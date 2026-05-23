"""Tests for ``skills_mcp.registry_api``.

The MCP server never talks HTTP directly — it shells out to ``gh api``. We
stub a ``gh`` binary that replays scripted JSON responses based on the API
endpoint and HTTP method passed on the command line. That keeps the tests
deterministic and entirely offline.
"""

from __future__ import annotations

import base64
import json
import stat
import textwrap
from pathlib import Path

import pytest

from skills_mcp import registry_api
from skills_mcp.registry_api import RegistryClient, slugify


@pytest.fixture
def fake_gh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
	"""Install a Python-based ``gh`` shim that echoes scripted responses.

	Tests write a JSON file describing ``[ {key, body, exit?}, ... ]``; the
	shim matches the first entry whose key is a substring of the joined
	argv and prints its body. Each match is consumed in order.
	"""
	import sys as _sys

	bin_dir = tmp_path / "bin"
	bin_dir.mkdir()
	state = tmp_path / "responses.json"
	state.write_text("[]")
	shim = bin_dir / "gh"
	# Use the actual interpreter path so the shim works even when PATH is
	# limited (and /usr/bin/env can't find python3).
	shim.write_text(
		textwrap.dedent(
			f"""\
			#!{_sys.executable}
			import json, sys, pathlib
			state = pathlib.Path({str(state)!r})
			data = json.loads(state.read_text())
			argv = " ".join(sys.argv[1:])
			for i, entry in enumerate(data):
				if entry["key"] in argv:
					body = entry.get("body", "")
					exit_code = entry.get("exit", 0)
					data.pop(i)
					state.write_text(json.dumps(data))
					if body:
						sys.stdout.write(body if isinstance(body, str) else json.dumps(body))
					sys.exit(exit_code)
			sys.stderr.write(f"unexpected gh call: {{argv}}\\n")
			sys.exit(99)
			"""
		)
	)
	shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
	monkeypatch.setattr(registry_api, "find_gh", lambda: shim)
	return state


def _enqueue(state_path: Path, entries: list[dict]) -> None:
	state_path.write_text(json.dumps(entries))


def test_slugify_normalizes_names() -> None:
	assert slugify("Code Review") == "code_review"
	assert slugify("  Trim Whitespace  ") == "trim_whitespace"
	assert slugify("!!!") == "skill"


def test_list_skills_returns_summaries(fake_gh: Path) -> None:
	frontmatter = textwrap.dedent(
		"""\
		---
		name: Code Review
		description: Helps with code review.
		---
		Body here.
		"""
	)
	encoded = base64.b64encode(frontmatter.encode()).decode()
	_enqueue(
		fake_gh,
		[
			{
				"key": "api -X GET repos/x/y/contents/",
				"body": [
					{"name": "code-review", "type": "dir", "sha": "tree-sha-1"},
					{"name": "README.md", "type": "file"},
					{"name": ".github", "type": "dir", "sha": "ignore"},
				],
			},
			{
				"key": "api -X GET repos/x/y/contents/code-review/SKILL.md",
				"body": {"encoding": "base64", "content": encoded},
			},
		],
	)
	client = RegistryClient(repo="x/y")
	summaries = client.list_skills()
	assert len(summaries) == 1
	assert summaries[0].slug == "code-review"
	assert summaries[0].name == "Code Review"
	assert "code review" in summaries[0].description.lower()


def test_list_skills_handles_empty_repo(fake_gh: Path) -> None:
	_enqueue(
		fake_gh,
		[
			{
				"key": "api -X GET repos/x/y/contents/",
				"body": "HTTP 404: Not Found",
				"exit": 1,
			}
		],
	)
	# Convert the 404 stderr-style response into something the shim emits as stderr.
	# Easier: just return [] for contents/, exercising the empty-folder branch.
	_enqueue(
		fake_gh,
		[{"key": "api -X GET repos/x/y/contents/", "body": []}],
	)
	client = RegistryClient(repo="x/y")
	assert client.list_skills() == []


def test_download_skill_writes_recursively(fake_gh: Path, tmp_path: Path) -> None:
	encoded_md = base64.b64encode(b"# SKILL").decode()
	encoded_extra = base64.b64encode(b"data").decode()
	_enqueue(
		fake_gh,
		[
			{
				"key": "api -X GET repos/x/y/contents/code-review",
				"body": [
					{"name": "SKILL.md", "type": "file"},
					{"name": "resources", "type": "dir"},
				],
			},
			{
				"key": "api -X GET repos/x/y/contents/code-review/SKILL.md",
				"body": {"encoding": "base64", "content": encoded_md},
			},
			{
				"key": "api -X GET repos/x/y/contents/code-review/resources",
				"body": [{"name": "extra.md", "type": "file"}],
			},
			{
				"key": "api -X GET repos/x/y/contents/code-review/resources/extra.md",
				"body": {"encoding": "base64", "content": encoded_extra},
			},
		],
	)
	client = RegistryClient(repo="x/y")
	dest = tmp_path / "out"
	result = client.download_skill("code-review", dest)
	assert result == dest
	assert (dest / "SKILL.md").read_bytes() == b"# SKILL"
	assert (dest / "resources" / "extra.md").read_bytes() == b"data"


def test_publish_skill_atomic_happy_path(fake_gh: Path) -> None:
	_enqueue(
		fake_gh,
		[
			# 1) head ref
			{
				"key": "api -X GET repos/x/y/git/ref/heads/main",
				"body": {"object": {"sha": "parent-sha"}},
			},
			# 2) parent commit
			{
				"key": "api -X GET repos/x/y/git/commits/parent-sha",
				"body": {"tree": {"sha": "base-tree"}},
			},
			# 3) recursive tree listing for stale-file detection
			{
				"key": "api -X GET repos/x/y/git/trees/base-tree",
				"body": {"tree": []},
			},
			# 4) blob create
			{
				"key": "api -X POST repos/x/y/git/blobs",
				"body": {"sha": "blob-sha"},
			},
			# 5) tree create
			{
				"key": "api -X POST repos/x/y/git/trees",
				"body": {"sha": "new-tree"},
			},
			# 6) commit create
			{
				"key": "api -X POST repos/x/y/git/commits",
				"body": {"sha": "new-commit"},
			},
			# 7) ref update
			{
				"key": "api -X PATCH repos/x/y/git/refs/heads/main",
				"body": {"object": {"sha": "new-commit"}},
			},
		],
	)
	client = RegistryClient(repo="x/y")
	sha = client.publish_skill("code-review", {"SKILL.md": b"# hello"})
	assert sha == "new-commit"


def test_publish_skill_retries_on_conflict(fake_gh: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# Speed up the test: shrink retry sleep.
	monkeypatch.setattr(registry_api, "_RETRY_BASE_DELAY_S", 0.0)

	def make_round(commit_sha: str, conflict: bool) -> list[dict]:
		ref_patch_body = (
			"HTTP 422: non-fast-forward" if conflict else {"object": {"sha": commit_sha}}
		)
		exit_code = 1 if conflict else 0
		return [
			{
				"key": "api -X GET repos/x/y/git/ref/heads/main",
				"body": {"object": {"sha": "parent"}},
			},
			{"key": "api -X GET repos/x/y/git/commits/parent", "body": {"tree": {"sha": "base"}}},
			{"key": "api -X GET repos/x/y/git/trees/base", "body": {"tree": []}},
			{"key": "api -X POST repos/x/y/git/blobs", "body": {"sha": "blob"}},
			{"key": "api -X POST repos/x/y/git/trees", "body": {"sha": "tree"}},
			{"key": "api -X POST repos/x/y/git/commits", "body": {"sha": commit_sha}},
			{
				"key": "api -X PATCH repos/x/y/git/refs/heads/main",
				"body": ref_patch_body if not conflict else "HTTP 422: non-fast-forward",
				"exit": exit_code,
			},
		]

	# Attempt 1 conflicts, attempt 2 succeeds.
	_enqueue(
		fake_gh,
		make_round("commit-1", conflict=True) + make_round("commit-2", conflict=False),
	)
	client = RegistryClient(repo="x/y")
	sha = client.publish_skill("code-review", {"SKILL.md": b"hello"})
	assert sha == "commit-2"
