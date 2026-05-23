"""``skill-registry-mcp`` — MCP server for a GitHub-backed skill registry.

Exposes three tools that talk to the user's registry repo via the GitHub CLI:

* ``list_skills`` — enumerate every skill in the registry.
* ``get_skill`` — download a skill into a local cache and return the path.
* ``publish_skill`` — atomically replace a skill folder in the registry.

The server is designed to run under desktop MCP clients (Claude Desktop,
Cursor, VS Code/Copilot) whose process environment doesn't inherit the
user's shell ``PATH``; see :mod:`skills_mcp.gh` and :mod:`skills_mcp.registry_api`.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from fastmcp import FastMCP

from . import __version__, cache
from .config import ConfigError
from .config import load as load_config
from .gh import GhNotAuthedError, GhNotFoundError, ensure_authed
from .registry_api import RegistryClient, slugify

log = logging.getLogger("skills_mcp.registry_server")

# Limit how many bytes a single publish call will accept. Prevents accidental
# uploads of huge binaries. Tunable via env if anyone ever needs more.
_MAX_FILE_BYTES = int(os.environ.get("SKILLS_MAX_FILE_BYTES", str(2 * 1024 * 1024)))


def build_server() -> FastMCP:
	"""Construct the FastMCP server. Validates auth + config at boot."""
	config = load_config()
	gh = ensure_authed()
	client = RegistryClient(repo=config.repo, default_branch=config.default_branch)
	# Use the gh we just verified rather than re-running PATH lookup later.
	client.gh = gh

	server = FastMCP(
		"skill-registry",
		instructions=(
			f"GitHub-backed skill registry at {config.repo}. "
			"Call `list_skills` to discover, `get_skill(slug=...)` to download, "
			"`publish_skill(...)` to upload."
		),
	)
	_register_tools(server, client, config.repo)
	log.info("Registry MCP server bound to %s (branch %s)", config.repo, config.default_branch)
	return server


def _register_tools(server: FastMCP, client: RegistryClient, repo: str) -> None:
	@server.tool(
		name="list_skills",
		description=(
			"List every skill in the user's GitHub skill registry. Returns a "
			"markdown table with slug, name, description, and the URI to fetch "
			"the skill via `get_skill`."
		),
		tags={"skills", "registry"},
	)
	def list_skills() -> str:
		summaries = client.list_skills()
		if not summaries:
			return f"No skills found in {repo}."
		header = (
			f"Registry: `{repo}` ({len(summaries)} skill"
			f"{'s' if len(summaries) != 1 else ''})\n\n"
			"| slug | name | description |\n"
			"| --- | --- | --- |\n"
		)
		rows = []
		for s in summaries:
			desc = s.description.replace("|", "\\|").replace("\n", " ")
			rows.append(f"| `{s.slug}` | {s.name} | {desc} |")
		footer = (
			'\n\nUse `get_skill(slug="<slug>")` to download a skill. The tool '
			"returns an absolute local path; read every file in that folder "
			"before acting on the skill."
		)
		return header + "\n".join(rows) + footer

	@server.tool(
		name="get_skill",
		description=(
			"Download a single skill from the registry into a local cache "
			"folder and return the absolute path. The folder contains "
			"`SKILL.md` plus any supporting files (e.g. `resources/`). "
			"Read every file in the returned folder before using the skill."
		),
		tags={"skills", "registry"},
	)
	def get_skill(slug: str) -> str:
		normalized = slugify(slug)
		current_sha = client.get_folder_sha(normalized)
		if current_sha is None:
			return f"Skill {slug!r} not found in {repo}."
		cached = cache.lookup(normalized)
		if cached is not None and cached.tree_sha == current_sha:
			log.info("Cache hit for %s (%s)", normalized, current_sha[:7])
			return str(cached.path)
		dest = cache.reserve(normalized)
		client.download_skill(normalized, dest)
		cache.commit(normalized, current_sha)
		log.info("Downloaded %s (%s)", normalized, current_sha[:7])
		return str(dest)

	@server.tool(
		name="publish_skill",
		description=(
			"Publish a skill to the registry. Provide either `files` (a "
			"mapping of path-relative-to-skill-folder → text content) or "
			"`local_folder` (an absolute path to a folder containing "
			"`SKILL.md`). Returns the new commit SHA on success."
		),
		tags={"skills", "registry"},
	)
	def publish_skill(
		name: str,
		files: dict[str, str] | None = None,
		local_folder: str | None = None,
	) -> str:
		if (files is None) == (local_folder is None):
			raise ValueError("Pass exactly one of `files` or `local_folder`.")
		slug = slugify(name)
		if files is None:
			payload = _collect_local_folder(Path(local_folder).expanduser().resolve())
		else:
			payload = {_normalize_rel_path(k): _encode_text(k, v) for k, v in files.items()}
		if "SKILL.md" not in payload:
			raise ValueError(
				"Skill must contain a top-level SKILL.md. Got: " + ", ".join(sorted(payload)) + "."
			)
		_validate_size(payload)
		commit_sha = client.publish_skill(slug, payload)
		return (
			f"Published `{slug}` to {repo}@{commit_sha[:7]}. "
			f"View: https://github.com/{repo}/tree/{commit_sha[:7]}/{slug}"
		)


def _normalize_rel_path(raw: str) -> str:
	rel = raw.replace(os.sep, "/")
	while rel.startswith("./"):
		rel = rel[2:]
	rel = rel.lstrip("/")
	if ".." in rel.split("/"):
		raise ValueError(f"Refusing path with '..' segments: {raw!r}")
	return rel


def _encode_text(key: str, value: str) -> bytes:
	if not isinstance(value, str):
		raise TypeError(f"`files[{key!r}]` must be a string; got {type(value).__name__}")
	return value.encode("utf-8")


def _collect_local_folder(folder: Path) -> dict[str, bytes]:
	if not folder.is_dir():
		raise FileNotFoundError(f"Not a directory: {folder}")
	out: dict[str, bytes] = {}
	for path in sorted(folder.rglob("*")):
		if not path.is_file():
			continue
		rel = path.relative_to(folder).as_posix()
		# Skip hidden noise — .DS_Store, .git, __pycache__, etc.
		if any(part.startswith(".") for part in rel.split("/")):
			continue
		if "__pycache__" in rel.split("/"):
			continue
		out[rel] = path.read_bytes()
	return out


def _validate_size(payload: dict[str, bytes]) -> None:
	for path, data in payload.items():
		if len(data) > _MAX_FILE_BYTES:
			raise ValueError(
				f"File {path!r} is {len(data)} bytes; limit is {_MAX_FILE_BYTES} "
				"(override with SKILLS_MAX_FILE_BYTES)."
			)


def main() -> int:
	logging.basicConfig(
		level=os.environ.get("SKILLS_LOG_LEVEL", "INFO").upper(),
		format="%(asctime)s %(levelname)s %(name)s: %(message)s",
		stream=sys.stderr,
	)
	try:
		server = build_server()
	except ConfigError as exc:
		print(f"skill-registry-mcp: {exc}", file=sys.stderr)
		return 2
	except GhNotFoundError as exc:
		print(f"skill-registry-mcp: {exc}", file=sys.stderr)
		return 3
	except GhNotAuthedError as exc:
		print(f"skill-registry-mcp: {exc}", file=sys.stderr)
		return 4
	server.run()
	return 0


__all__ = ["build_server", "main", "__version__"]


if __name__ == "__main__":
	sys.exit(main())
