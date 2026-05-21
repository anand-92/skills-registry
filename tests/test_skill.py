"""Tests for the ``Skill`` class."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from skills_mcp.__main__ import Skill


def test_skill_uses_folder_name_when_no_frontmatter(tmp_path: Path, make_skill: Any) -> None:
	main = make_skill(tmp_path, "my-folder", body="Hello body.")
	skill = Skill(root=tmp_path, folder=main.parent, main_file=main)
	assert skill.name == "my-folder"
	assert skill.slug == "my_folder"
	assert skill.description == "Hello body."
	assert skill.root == tmp_path
	assert skill.folder == main.parent
	assert skill.main_file == main


def test_skill_frontmatter_overrides_name(tmp_path: Path, make_skill: Any) -> None:
	main = make_skill(
		tmp_path,
		"folder-name",
		body="Body.",
		frontmatter={"name": "Pretty Name"},
	)
	skill = Skill(root=tmp_path, folder=main.parent, main_file=main)
	assert skill.name == "Pretty Name"
	assert skill.slug == "pretty_name"


def test_skill_frontmatter_overrides_description(tmp_path: Path, make_skill: Any) -> None:
	main = make_skill(
		tmp_path,
		"d",
		body="Ignored body paragraph.",
		frontmatter={"description": "Explicit description."},
	)
	skill = Skill(root=tmp_path, folder=main.parent, main_file=main)
	assert skill.description == "Explicit description."


def test_skill_description_falls_back_to_first_paragraph(tmp_path: Path, make_skill: Any) -> None:
	main = make_skill(
		tmp_path,
		"only-body",
		body="# Heading\n\nFallback paragraph for description.",
	)
	skill = Skill(root=tmp_path, folder=main.parent, main_file=main)
	assert skill.description == "Fallback paragraph for description."


def test_skill_description_placeholder_when_no_paragraph(tmp_path: Path, make_skill: Any) -> None:
	# Empty body and no description in frontmatter → placeholder.
	main = make_skill(tmp_path, "empty-body", body="", frontmatter={"name": "Nameless"})
	skill = Skill(root=tmp_path, folder=main.parent, main_file=main)
	assert skill.description == "Skill: Nameless"


def test_skill_slug_normalizes_folder_name(tmp_path: Path, make_skill: Any) -> None:
	main = make_skill(tmp_path, "Weird Folder Name!", body="body")
	skill = Skill(root=tmp_path, folder=main.parent, main_file=main)
	assert skill.slug == "weird_folder_name"


def test_skill_handles_non_utf8_bytes(tmp_path: Path) -> None:
	folder = tmp_path / "binary-ish"
	folder.mkdir()
	main = folder / "SKILL.md"
	# Invalid UTF-8 byte should be replaced rather than crash.
	main.write_bytes(b"---\nname: Bin\n---\nHello \xff world.")
	skill = Skill(root=tmp_path, folder=folder, main_file=main)
	assert skill.name == "Bin"
	assert "Hello" in skill.description


def test_skill_description_truncated_to_240_chars(tmp_path: Path, make_skill: Any) -> None:
	long = "a" * 500
	main = make_skill(tmp_path, "long-body", body=long)
	skill = Skill(root=tmp_path, folder=main.parent, main_file=main)
	assert len(skill.description) == 240
