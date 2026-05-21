"""Tests for ``skills_mcp.__main__._parse_roots``."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from skills_mcp.__main__ import _parse_roots


def test_single_existing_root(tmp_path: Path) -> None:
	roots = _parse_roots(str(tmp_path))
	assert roots == [tmp_path.resolve()]


def test_multi_root_split_on_pathsep(tmp_path: Path) -> None:
	a = tmp_path / "a"
	b = tmp_path / "b"
	a.mkdir()
	b.mkdir()
	raw = f"{a}{os.pathsep}{b}"
	roots = _parse_roots(raw)
	assert roots == [a.resolve(), b.resolve()]


def test_empty_string_raises_systemexit() -> None:
	with pytest.raises(SystemExit) as excinfo:
		_parse_roots("")
	assert "SKILLS_ROOT" in str(excinfo.value)


def test_whitespace_only_raises_systemexit() -> None:
	with pytest.raises(SystemExit):
		_parse_roots("   ")


def test_missing_directory_raises_systemexit(tmp_path: Path) -> None:
	missing = tmp_path / "does-not-exist"
	with pytest.raises(SystemExit) as excinfo:
		_parse_roots(str(missing))
	assert "not found" in str(excinfo.value) or "not a directory" in str(excinfo.value)


def test_file_path_is_rejected(tmp_path: Path) -> None:
	file = tmp_path / "not-a-dir.txt"
	file.write_text("hello", encoding="utf-8")
	with pytest.raises(SystemExit):
		_parse_roots(str(file))


def test_tilde_is_expanded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	monkeypatch.setenv("HOME", str(tmp_path))
	# On Windows, Path.expanduser uses USERPROFILE.
	monkeypatch.setenv("USERPROFILE", str(tmp_path))
	roots = _parse_roots("~")
	assert roots == [tmp_path.resolve()]


def test_empty_segments_are_skipped(tmp_path: Path) -> None:
	# Leading/trailing/internal pathsep produces empty parts that must be skipped.
	raw = f"{os.pathsep}{tmp_path}{os.pathsep}{os.pathsep}"
	roots = _parse_roots(raw)
	assert roots == [tmp_path.resolve()]


def test_partial_missing_root_is_rejected(tmp_path: Path) -> None:
	good = tmp_path / "good"
	good.mkdir()
	bad = tmp_path / "missing"
	with pytest.raises(SystemExit) as excinfo:
		_parse_roots(f"{good}{os.pathsep}{bad}")
	assert str(bad) in str(excinfo.value) or "missing" in str(excinfo.value)
