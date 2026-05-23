"""Tests for ``skills_mcp.registry_server``.

We exercise the helper functions directly (path normalization, folder
collection, size validation) and verify ``build_server`` fails fast when
config or auth is missing.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastmcp import FastMCP

from skills_mcp import registry_server
from skills_mcp.config import ConfigError


def test_normalize_rel_path_strips_leading(monkeypatch: pytest.MonkeyPatch) -> None:
	assert registry_server._normalize_rel_path("./SKILL.md") == "SKILL.md"
	assert registry_server._normalize_rel_path("/foo/bar.md") == "foo/bar.md"


def test_normalize_rel_path_rejects_traversal() -> None:
	with pytest.raises(ValueError, match=r"\.\."):
		registry_server._normalize_rel_path("../escape.md")


def test_encode_text_rejects_non_string() -> None:
	with pytest.raises(TypeError):
		registry_server._encode_text("k", 123)  # type: ignore[arg-type]


def test_collect_local_folder_skips_hidden(tmp_path: Path) -> None:
	(tmp_path / "SKILL.md").write_text("# hi")
	(tmp_path / ".DS_Store").write_text("noise")
	subdir = tmp_path / "resources"
	subdir.mkdir()
	(subdir / "a.md").write_text("extra")
	hidden_dir = tmp_path / ".git"
	hidden_dir.mkdir()
	(hidden_dir / "HEAD").write_text("ref")
	cache_dir = tmp_path / "__pycache__"
	cache_dir.mkdir()
	(cache_dir / "x.pyc").write_text("noise")

	collected = registry_server._collect_local_folder(tmp_path)
	assert set(collected) == {"SKILL.md", "resources/a.md"}


def test_collect_local_folder_missing(tmp_path: Path) -> None:
	with pytest.raises(FileNotFoundError):
		registry_server._collect_local_folder(tmp_path / "nope")


def test_validate_size_enforces_limit(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(registry_server, "_MAX_FILE_BYTES", 100)
	with pytest.raises(ValueError, match="bytes; limit"):
		registry_server._validate_size({"big.md": b"x" * 200})


def test_build_server_fails_fast_without_config(
	monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
	monkeypatch.delenv("SKILLS_REGISTRY", raising=False)
	monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
	with pytest.raises(ConfigError):
		registry_server.build_server()


def test_main_exits_with_config_error_code(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
	capsys: pytest.CaptureFixture[str],
) -> None:
	monkeypatch.delenv("SKILLS_REGISTRY", raising=False)
	monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
	rc = registry_server.main()
	assert rc == 2
	captured = capsys.readouterr()
	assert "No registry configured" in captured.err


def test_register_tools_exposes_three_tools_with_correct_metadata() -> None:
	"""Direct ``_register_tools`` smoke check — no gh/config plumbing."""
	server = FastMCP("test")
	fake_client = SimpleNamespace(
		list_skills=lambda: [],
		get_folder_sha=lambda slug: None,
		download_skill=lambda slug, dest: dest,
		publish_skill=lambda slug, payload: "deadbeef",
	)
	registry_server._register_tools(server, fake_client, "fake/repo")

	tools = {t.name: t for t in asyncio.run(server.list_tools())}
	assert set(tools) == {"list_skills", "get_skill", "publish_skill"}

	# Safety hints (the only annotations clients gate on).
	assert tools["list_skills"].annotations.readOnlyHint is True
	assert tools["get_skill"].annotations.readOnlyHint is True
	assert tools["publish_skill"].annotations.destructiveHint is True

	# ``Args:`` docstring on publish_skill propagates to per-param descriptions.
	publish_props = tools["publish_skill"].parameters["properties"]
	assert publish_props["files"]["description"]
	assert publish_props["local_folder"]["description"]
