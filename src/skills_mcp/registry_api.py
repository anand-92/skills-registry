"""High-level registry client built on top of ``gh api``.

All registry I/O goes through this module so the MCP server (and any future
callers) never shell out to ``git`` or talk to GitHub HTTP directly. That
avoids two whole categories of pain in GUI MCP clients:

* Missing ``git`` binary or SSH agent (``SSH_AUTH_SOCK`` unset).
* Missing global ``user.name`` / ``user.email``.

Writes use the Git Data API (blobs → tree → commit → ref update), so updates
to a folder don't clobber sibling skills, and a 422 non-fast-forward triggers
a retry against the freshly-fetched HEAD.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from .gh import GhApiError, find_gh, gh_api

log = logging.getLogger("skills_mcp.registry_api")

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_MAX_RETRIES = 3
_RETRY_BASE_DELAY_S = 0.5


def slugify(name: str) -> str:
	"""Match :func:`skills_mcp.__main__._slug` so slugs stay consistent."""
	return _SLUG_RE.sub("_", name.strip().lower()).strip("_") or "skill"


@dataclass(frozen=True)
class SkillSummary:
	"""One row in the registry listing."""

	slug: str
	name: str
	description: str
	path: str  # directory path in the registry (usually == slug)
	tree_sha: str  # SHA of the skill folder's tree (for cache invalidation)


class RegistryConflictError(RuntimeError):
	"""Raised when an atomic publish can't be reconciled after retries."""


class RegistryClient:
	"""Thin wrapper around ``gh api`` for one registry repo."""

	def __init__(self, repo: str, default_branch: str = "main") -> None:
		self.repo = repo
		self.default_branch = default_branch
		self.gh = find_gh()

	# ------------------------------------------------------------------ reads

	def list_skills(self) -> list[SkillSummary]:
		"""Enumerate top-level skill folders in the registry."""
		try:
			entries = gh_api(f"repos/{self.repo}/contents/", gh=self.gh)
		except GhApiError as exc:
			if exc.status == 404:
				return []
			raise
		if not isinstance(entries, list):
			return []
		out: list[SkillSummary] = []
		for entry in entries:
			if entry.get("type") != "dir":
				continue
			slug = entry["name"]
			if slug.startswith(".") or slug in {"node_modules", "__pycache__"}:
				continue
			summary = self._summarize_folder(slug, entry.get("sha", ""))
			if summary is not None:
				out.append(summary)
		out.sort(key=lambda s: s.slug)
		return out

	def _summarize_folder(self, slug: str, tree_sha: str) -> SkillSummary | None:
		"""Fetch ``<slug>/SKILL.md`` and parse its frontmatter for the listing."""
		try:
			meta = gh_api(f"repos/{self.repo}/contents/{slug}/SKILL.md", gh=self.gh)
		except GhApiError as exc:
			if exc.status == 404:
				return None
			raise
		if not isinstance(meta, dict) or meta.get("encoding") != "base64":
			return None
		content = base64.b64decode(meta["content"]).decode("utf-8", errors="replace")
		name, description = _parse_skill_md(content, default_name=slug)
		return SkillSummary(
			slug=slug,
			name=name,
			description=description,
			path=slug,
			tree_sha=tree_sha,
		)

	def download_skill(self, slug: str, dest: Path) -> Path:
		"""Recursively copy ``<slug>/`` from the registry into ``dest``.

		``dest`` is treated as the target skill folder (e.g. ``…/my-skills/foo``).
		Returns the resolved destination path. Existing files at ``dest`` are
		overwritten.
		"""
		dest.mkdir(parents=True, exist_ok=True)
		self._download_recursive(slug, dest)
		return dest

	def _download_recursive(self, repo_path: str, dest_dir: Path) -> None:
		try:
			entries = gh_api(f"repos/{self.repo}/contents/{repo_path}", gh=self.gh)
		except GhApiError as exc:
			if exc.status == 404:
				raise FileNotFoundError(f"skill {repo_path!r} not found in {self.repo}") from exc
			raise
		if not isinstance(entries, list):
			# Single-file response — caller asked for a file path, not a folder.
			entries = [entries]
		dest_dir.mkdir(parents=True, exist_ok=True)
		for entry in entries:
			name = entry["name"]
			if entry["type"] == "dir":
				self._download_recursive(f"{repo_path}/{name}", dest_dir / name)
			elif entry["type"] == "file":
				blob = gh_api(f"repos/{self.repo}/contents/{repo_path}/{name}", gh=self.gh)
				if not isinstance(blob, dict) or blob.get("encoding") != "base64":
					continue
				data = base64.b64decode(blob["content"])
				(dest_dir / name).write_bytes(data)

	def get_folder_sha(self, slug: str) -> str | None:
		"""Return the tree SHA of ``<slug>/`` for cache invalidation, or None."""
		try:
			entries = gh_api(f"repos/{self.repo}/contents/", gh=self.gh)
		except GhApiError as exc:
			if exc.status == 404:
				return None
			raise
		if not isinstance(entries, list):
			return None
		for entry in entries:
			if entry.get("name") == slug and entry.get("type") == "dir":
				return entry.get("sha")
		return None

	# ----------------------------------------------------------------- writes

	def publish_skill(
		self,
		slug: str,
		files: dict[str, bytes],
		*,
		commit_message: str | None = None,
	) -> str:
		"""Atomically replace ``<slug>/`` with ``files`` (path → bytes).

		``files`` keys are paths *relative to the skill folder*, e.g.
		``{"SKILL.md": b"...", "resources/a.md": b"..."}``. Existing files in
		``<slug>/`` not present in ``files`` are removed (folder reset). Other
		top-level folders are untouched.

		Returns the SHA of the new commit. Raises
		:class:`RegistryConflictError` after the retry budget is exhausted.
		"""
		commit_message = commit_message or f"publish: {slug}"
		last_err: GhApiError | None = None
		for attempt in range(_MAX_RETRIES):
			try:
				return self._publish_once(slug, files, commit_message)
			except GhApiError as exc:
				# 409/422 = concurrent push; refetch HEAD and retry.
				if exc.status not in {409, 422}:
					raise
				last_err = exc
				delay = _RETRY_BASE_DELAY_S * (2**attempt)
				log.warning(
					"publish_skill conflict on attempt %d/%d (%s); retrying in %.1fs",
					attempt + 1,
					_MAX_RETRIES,
					exc.status,
					delay,
				)
				time.sleep(delay)
		raise RegistryConflictError(
			f"Could not publish {slug!r} after {_MAX_RETRIES} attempts: {last_err}"
		)

	def _publish_once(self, slug: str, files: dict[str, bytes], message: str) -> str:
		# 1) Fetch ref head + tree SHA
		ref = gh_api(f"repos/{self.repo}/git/ref/heads/{self.default_branch}", gh=self.gh)
		if not isinstance(ref, dict):
			raise GhApiError(f"git/ref/heads/{self.default_branch}", "GET", 0, str(ref))
		parent_sha = ref["object"]["sha"]
		commit = gh_api(f"repos/{self.repo}/git/commits/{parent_sha}", gh=self.gh)
		if not isinstance(commit, dict):
			raise GhApiError(f"git/commits/{parent_sha}", "GET", 0, str(commit))
		base_tree_sha = commit["tree"]["sha"]

		# 2) Get the previous list of paths under <slug>/ so we can delete strays.
		previous_paths = self._list_tree_paths_under(base_tree_sha, slug)

		# 3) Create blobs for every new file.
		tree_entries: list[dict] = []
		incoming_paths: set[str] = set()
		for rel_path, content in files.items():
			rel_norm = rel_path.replace(os.sep, "/").lstrip("/")
			incoming_paths.add(rel_norm)
			blob = gh_api(
				f"repos/{self.repo}/git/blobs",
				method="POST",
				input_json={
					"content": base64.b64encode(content).decode("ascii"),
					"encoding": "base64",
				},
				gh=self.gh,
			)
			if not isinstance(blob, dict) or "sha" not in blob:
				raise GhApiError(f"repos/{self.repo}/git/blobs", "POST", 0, json.dumps(blob))
			tree_entries.append(
				{
					"path": f"{slug}/{rel_norm}",
					"mode": "100644",
					"type": "blob",
					"sha": blob["sha"],
				}
			)

		# 4) Stale files under <slug>/ get a null sha so the tree removes them.
		for stale in sorted(previous_paths - incoming_paths):
			tree_entries.append(
				{
					"path": f"{slug}/{stale}",
					"mode": "100644",
					"type": "blob",
					"sha": None,
				}
			)

		# 5) Create the new tree on top of the base tree (so other top-level
		#    skills stay intact).
		new_tree = gh_api(
			f"repos/{self.repo}/git/trees",
			method="POST",
			input_json={"base_tree": base_tree_sha, "tree": tree_entries},
			gh=self.gh,
		)
		if not isinstance(new_tree, dict) or "sha" not in new_tree:
			raise GhApiError(f"repos/{self.repo}/git/trees", "POST", 0, json.dumps(new_tree))

		# 6) Commit referencing the new tree.
		new_commit = gh_api(
			f"repos/{self.repo}/git/commits",
			method="POST",
			input_json={
				"message": message,
				"tree": new_tree["sha"],
				"parents": [parent_sha],
			},
			gh=self.gh,
		)
		if not isinstance(new_commit, dict) or "sha" not in new_commit:
			raise GhApiError(f"repos/{self.repo}/git/commits", "POST", 0, json.dumps(new_commit))

		# 7) Fast-forward the ref.
		gh_api(
			f"repos/{self.repo}/git/refs/heads/{self.default_branch}",
			method="PATCH",
			input_json={"sha": new_commit["sha"], "force": False},
			gh=self.gh,
		)
		return new_commit["sha"]

	def _list_tree_paths_under(self, root_tree_sha: str, sub_path: str) -> set[str]:
		"""Return every blob path under ``sub_path`` (relative to the subfolder).

		Used to detect stale files we need to delete on publish. Walks the
		recursive tree once via the Git Trees API.
		"""
		try:
			result = gh_api(
				f"repos/{self.repo}/git/trees/{root_tree_sha}",
				fields={"recursive": "1"},
				gh=self.gh,
			)
		except GhApiError as exc:
			if exc.status == 404:
				return set()
			raise
		if not isinstance(result, dict):
			return set()
		prefix = f"{sub_path}/"
		paths: set[str] = set()
		for entry in result.get("tree", []):
			if entry.get("type") != "blob":
				continue
			path = entry.get("path", "")
			if path.startswith(prefix):
				paths.add(path[len(prefix) :])
		return paths


# --- standalone helpers --------------------------------------------------


def _parse_skill_md(text: str, *, default_name: str) -> tuple[str, str]:
	"""Pull ``name`` and ``description`` from frontmatter; fall back to body."""
	from .__main__ import _first_paragraph, _parse_frontmatter

	meta, body = _parse_frontmatter(text)
	name = meta.get("name", default_name).strip() or default_name
	description = meta.get("description") or _first_paragraph(body)
	# Description in frontmatter can be a folded scalar with newlines — collapse.
	description = " ".join(description.split())
	return name, description[:300]
