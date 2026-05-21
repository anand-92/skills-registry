"""Tests for ``skills_mcp.__main__.main`` (the CLI entry point)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from skills_mcp import __version__
from skills_mcp.__main__ import main


def test_version_flag_exits_zero_and_prints_version(
	capsys: pytest.CaptureFixture[str],
) -> None:
	with pytest.raises(SystemExit) as excinfo:
		main(["--version"])
	# argparse exits with code 0 on --version.
	assert excinfo.value.code == 0
	captured = capsys.readouterr()
	combined = captured.out + captured.err
	assert __version__ in combined
	assert "skills-mcp" in combined


def test_list_prints_rows_and_returns_zero(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
	capsys: pytest.CaptureFixture[str],
	make_skill: Any,
) -> None:
	make_skill(tmp_path, "alpha", body="A body.", frontmatter={"name": "Alpha"})
	make_skill(tmp_path, "bravo", body="B body.", frontmatter={"name": "Bravo"})
	monkeypatch.setenv("SKILLS_ROOT", str(tmp_path))

	rc = main(["--list"])
	assert rc == 0
	out = capsys.readouterr().out.strip().splitlines()
	# Two rows, each tab-separated "slug\tname\tfolder".
	assert len(out) == 2
	for line in out:
		parts = line.split("\t")
		assert len(parts) == 3
		slug, name, folder = parts
		assert slug in {"alpha", "bravo"}
		assert name in {"Alpha", "Bravo"}
		assert Path(folder).is_dir()


def test_list_empty_root_returns_one_with_stderr_message(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
	capsys: pytest.CaptureFixture[str],
) -> None:
	monkeypatch.setenv("SKILLS_ROOT", str(tmp_path))
	rc = main(["--list"])
	assert rc == 1
	captured = capsys.readouterr()
	assert captured.out == ""
	assert "No skills found" in captured.err


def test_list_missing_root_raises_systemexit(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	monkeypatch.setenv("SKILLS_ROOT", str(tmp_path / "missing-dir"))
	with pytest.raises(SystemExit):
		main(["--list"])


def test_list_respects_custom_main_file_name(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
	capsys: pytest.CaptureFixture[str],
	make_skill: Any,
) -> None:
	make_skill(tmp_path, "custom", body="x", main_file_name="INSTRUCTIONS.md")
	monkeypatch.setenv("SKILLS_ROOT", str(tmp_path))
	monkeypatch.setenv("SKILLS_MAIN_FILE_NAME", "INSTRUCTIONS.md")
	rc = main(["--list"])
	assert rc == 0
	assert "custom" in capsys.readouterr().out
