"""Entry point: ``python -m skills_mcp`` and the ``skills-mcp`` console script."""

from __future__ import annotations

import argparse
import logging
import mimetypes
import os
import re
import sys
from collections.abc import Iterable
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.resources import FileResource

from . import __version__

log = logging.getLogger("skills_mcp")

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(name: str) -> str:
	return _SLUG_RE.sub("_", name.strip().lower()).strip("_") or "skill"


def _parse_roots(raw: str) -> list[Path]:
	parts = [p for p in raw.split(os.pathsep) if p.strip()]
	if not parts:
		raise SystemExit(
			"SKILLS_ROOT is empty. Set it to a directory of skills (e.g. ~/my-skills)."
		)
	roots = [Path(p).expanduser().resolve() for p in parts]
	missing = [str(p) for p in roots if not p.is_dir()]
	if missing:
		raise SystemExit("SKILLS_ROOT path(s) not found or not a directory: " + ", ".join(missing))
	return roots


def _parse_bool(name: str, default: bool) -> bool:
	val = os.environ.get(name)
	if val is None:
		return default
	v = val.strip().lower()
	if v in {"1", "true", "yes", "on"}:
		return True
	if v in {"0", "false", "no", "off"}:
		return False
	raise SystemExit(f"{name} must be a boolean (true/false), got: {val!r}")


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
	"""Extract a flat YAML-ish frontmatter block (``--- ... ---``) from the top of a file.

	Returns ``(meta, body)``. Only ``key: value`` lines are recognized — we intentionally
	avoid a YAML dependency for this tiny use case.
	"""
	if not text.startswith("---"):
		return {}, text
	lines = text.splitlines()
	end = None
	for i in range(1, len(lines)):
		if lines[i].strip() == "---":
			end = i
			break
	if end is None:
		return {}, text
	meta: dict[str, str] = {}
	for raw in lines[1:end]:
		if ":" in raw and not raw.lstrip().startswith("#"):
			k, v = raw.split(":", 1)
			meta[k.strip()] = v.strip().strip('"').strip("'")
	body = "\n".join(lines[end + 1 :]).lstrip("\n")
	return meta, body


def _first_paragraph(text: str, limit: int = 240) -> str:
	for block in text.split("\n\n"):
		cleaned = " ".join(block.strip().split())
		if cleaned and not cleaned.startswith("#"):
			return cleaned[:limit]
	return text.strip()[:limit]


class Skill:
	__slots__ = ("root", "folder", "name", "slug", "description", "main_file")

	def __init__(self, root: Path, folder: Path, main_file: Path) -> None:
		text = main_file.read_text(encoding="utf-8", errors="replace")
		meta, body = _parse_frontmatter(text)
		self.root = root
		self.folder = folder
		self.main_file = main_file
		raw_name = meta.get("name") or folder.name
		self.name = raw_name
		self.slug = _slug(raw_name)
		self.description = meta.get("description") or _first_paragraph(body) or f"Skill: {raw_name}"


def discover_skills(roots: Iterable[Path], main_file_name: str) -> list[Skill]:
	skills: list[Skill] = []
	seen: set[str] = set()
	for root in roots:
		for main in sorted(root.rglob(main_file_name)):
			if not main.is_file():
				continue
			folder = main.parent
			skill = Skill(root=root, folder=folder, main_file=main)
			if skill.slug in seen:
				log.warning(
					"Duplicate skill slug %r (from %s) — keeping the first occurrence.",
					skill.slug,
					folder,
				)
				continue
			seen.add(skill.slug)
			skills.append(skill)
	return skills


def _register_skill(mcp: FastMCP, skill: Skill, scheme: str, expose_tools: bool) -> None:
	main_uri = f"{scheme}://{skill.slug}/{skill.main_file.name}"
	mcp.add_resource(
		FileResource(
			uri=main_uri,
			path=skill.main_file,
			name=skill.name,
			description=skill.description,
			mime_type="text/markdown",
			tags={"skill"},
		)
	)

	# Supporting files: everything else under the skill folder.
	for path in sorted(skill.folder.rglob("*")):
		if not path.is_file() or path == skill.main_file:
			continue
		rel = path.relative_to(skill.folder).as_posix()
		uri = f"{scheme}://{skill.slug}/{rel}"
		mime, _ = mimetypes.guess_type(path.name)
		is_binary = mime is not None and not (
			mime.startswith("text/") or mime in {"application/json", "application/xml"}
		)
		mcp.add_resource(
			FileResource(
				uri=uri,
				path=path,
				name=f"{skill.name}:{rel}",
				description=f"Supporting file for skill {skill.name!r}.",
				mime_type=mime or "text/plain",
				is_binary=is_binary,
				tags={"skill", "skill-resource"},
			)
		)

	if expose_tools:
		main_path = skill.main_file
		tool_name = f"skill_{skill.slug}"

		def _load_skill() -> str:
			return main_path.read_text(encoding="utf-8", errors="replace")

		_load_skill.__name__ = tool_name
		_load_skill.__doc__ = skill.description
		mcp.tool(
			name=tool_name,
			description=skill.description,
			tags={"skill"},
		)(_load_skill)


def build_server() -> FastMCP:
	default_root = str(Path.home() / "my-skills")
	roots = _parse_roots(os.environ.get("SKILLS_ROOT", default_root))
	main_file = os.environ.get("SKILLS_MAIN_FILE_NAME", "SKILL.md").strip() or "SKILL.md"
	server_name = os.environ.get("SKILLS_SERVER_NAME", "skills").strip() or "skills"
	scheme = os.environ.get("SKILLS_RESOURCE_SCHEME", "skill").strip() or "skill"
	expose_tools = _parse_bool("SKILLS_EXPOSE_TOOLS", True)

	mcp = FastMCP(
		server_name,
		instructions=(
			"This server exposes a directory of Markdown skills. "
			"Each skill is available as a resource (and, by default, a tool); "
			"invoke a skill tool to load its instructions."
		),
	)

	skills = discover_skills(roots, main_file)
	for skill in skills:
		_register_skill(mcp, skill, scheme=scheme, expose_tools=expose_tools)

	log.info(
		"Loaded %d skill(s) from %s",
		len(skills),
		", ".join(str(r) for r in roots),
	)
	return mcp


def _cmd_list() -> int:
	roots = _parse_roots(os.environ.get("SKILLS_ROOT", str(Path.home() / "my-skills")))
	main_file = os.environ.get("SKILLS_MAIN_FILE_NAME", "SKILL.md")
	skills = discover_skills(roots, main_file)
	if not skills:
		print("No skills found.", file=sys.stderr)
		return 1
	for s in skills:
		print(f"{s.slug}\t{s.name}\t{s.folder}")
	return 0


def _cmd_serve() -> int:
	build_server().run()
	return 0


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(
		prog="skills-mcp",
		description=(
			"MCP server that exposes a directory of Markdown SKILL.md files "
			"as resources/tools to any MCP-compatible client."
		),
	)
	parser.add_argument(
		"--version",
		action="version",
		version=f"skills-mcp {__version__}",
	)
	parser.add_argument(
		"--list",
		action="store_true",
		help="List discovered skills and exit (alias for `skills-mcp list`).",
	)

	subparsers = parser.add_subparsers(dest="command", metavar="<command>")
	subparsers.add_parser(
		"serve",
		help="Run the MCP server (default when no command is given).",
	)
	subparsers.add_parser(
		"list",
		help="List discovered skills and exit.",
	)

	# `gather` subcommand is defined in its own module to keep this file small.
	from .gather import register_subparser as _register_gather

	_register_gather(subparsers)

	args = parser.parse_args(argv)

	logging.basicConfig(
		level=os.environ.get("SKILLS_LOG_LEVEL", "INFO").upper(),
		format="%(asctime)s %(levelname)s %(name)s: %(message)s",
		stream=sys.stderr,
	)

	if args.command == "gather":
		from .gather import cmd_gather

		return cmd_gather(args)

	if args.list or args.command == "list":
		return _cmd_list()

	return _cmd_serve()


if __name__ == "__main__":
	sys.exit(main())
