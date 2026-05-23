"""Tests for ``skills_mcp.gh``."""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from skills_mcp import gh


def _make_fake_binary(path: Path, exit_code: int = 0, stdout: str = "") -> Path:
	path.parent.mkdir(parents=True, exist_ok=True)
	# Use sh because exec doesn't honor shebang at execv from gh subprocess in some setups.
	path.write_text("#!/bin/sh\ncat <<'EOF'\n" + stdout + "\nEOF\nexit " + str(exit_code) + "\n")
	path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
	return path


def test_find_gh_uses_path_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	gh_path = _make_fake_binary(tmp_path / "gh")
	monkeypatch.setenv("PATH", str(tmp_path))
	assert gh.find_gh() == gh_path


def test_find_gh_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setenv("PATH", "/nonexistent")
	monkeypatch.setattr(gh, "_FALLBACK_GH_PATHS", ())
	with pytest.raises(gh.GhNotFoundError, match="not found"):
		gh.find_gh()


def test_find_gh_fallback_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	monkeypatch.setenv("PATH", "/nonexistent")
	fake = _make_fake_binary(tmp_path / "alt" / "gh")
	monkeypatch.setattr(gh, "_FALLBACK_GH_PATHS", (fake,))
	assert gh.find_gh() == fake


def test_ensure_authed_passes_through(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	gh_path = _make_fake_binary(tmp_path / "gh", exit_code=0)
	monkeypatch.setenv("PATH", str(tmp_path))
	monkeypatch.setattr(gh, "_FALLBACK_GH_PATHS", ())
	assert gh.ensure_authed() == gh_path


def test_ensure_authed_raises_on_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	_make_fake_binary(tmp_path / "gh", exit_code=1)
	monkeypatch.setenv("PATH", str(tmp_path))
	monkeypatch.setattr(gh, "_FALLBACK_GH_PATHS", ())
	with pytest.raises(gh.GhNotAuthedError):
		gh.ensure_authed()


def test_gh_api_returns_parsed_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	gh_path = _make_fake_binary(
		tmp_path / "gh",
		stdout=json.dumps({"hello": "world"}),
	)
	result = gh.gh_api("repos/x/y", gh=gh_path)
	assert result == {"hello": "world"}


def test_gh_api_error_surfaces_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	bad = tmp_path / "gh"
	bad.write_text("#!/bin/sh\necho 'HTTP 422: Unprocessable Entity' 1>&2\nexit 1\n")
	bad.chmod(bad.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
	with pytest.raises(gh.GhApiError) as exc_info:
		gh.gh_api("repos/x/y", gh=bad)
	assert exc_info.value.status == 422
