"""Tests for ``skills_mcp.__main__.discover_skills``."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from skills_mcp.__main__ import discover_skills


def test_discovers_single_skill(tmp_path: Path, make_skill: Any) -> None:
	make_skill(tmp_path, "alpha", body="alpha body")
	skills = discover_skills([tmp_path], "SKILL.md")
	assert len(skills) == 1
	assert skills[0].slug == "alpha"
	assert skills[0].name == "alpha"


def test_discovers_multiple_skills_sorted(tmp_path: Path, make_skill: Any) -> None:
	make_skill(tmp_path, "bravo", body="b")
	make_skill(tmp_path, "alpha", body="a")
	make_skill(tmp_path, "charlie", body="c")
	skills = discover_skills([tmp_path], "SKILL.md")
	slugs = [s.slug for s in skills]
	# rglob is sorted at call-site, so we expect deterministic order.
	assert sorted(slugs) == slugs
	assert set(slugs) == {"alpha", "bravo", "charlie"}


def test_discovers_nested_skills(tmp_path: Path, make_skill: Any) -> None:
	nested = tmp_path / "category"
	nested.mkdir()
	make_skill(nested, "nested-skill", body="x")
	make_skill(tmp_path, "top-level", body="y")
	skills = discover_skills([tmp_path], "SKILL.md")
	slugs = {s.slug for s in skills}
	assert slugs == {"nested_skill", "top_level"}


def test_empty_root_returns_empty_list(tmp_path: Path) -> None:
	assert discover_skills([tmp_path], "SKILL.md") == []


def test_no_match_when_main_file_name_differs(tmp_path: Path, make_skill: Any) -> None:
	make_skill(tmp_path, "x", body="b")
	assert discover_skills([tmp_path], "OTHER.md") == []


def test_custom_main_file_name(tmp_path: Path, make_skill: Any) -> None:
	make_skill(tmp_path, "y", body="body", main_file_name="INSTRUCTIONS.md")
	skills = discover_skills([tmp_path], "INSTRUCTIONS.md")
	assert len(skills) == 1
	assert skills[0].slug == "y"


def test_duplicate_slug_keeps_first_and_warns(
	tmp_path: Path,
	make_skill: Any,
	caplog: pytest.LogCaptureFixture,
) -> None:
	# Two folders that slugify to the same value.
	make_skill(tmp_path, "hello-world", body="first", frontmatter={"name": "hello-world"})
	make_skill(tmp_path, "Hello World", body="second", frontmatter={"name": "Hello World"})
	with caplog.at_level(logging.WARNING, logger="skills_mcp"):
		skills = discover_skills([tmp_path], "SKILL.md")
	assert len(skills) == 1
	assert skills[0].slug == "hello_world"
	# The kept skill is the first one encountered (sorted rglob -> "Hello World" comes first
	# alphabetically because uppercase sorts before lowercase in ASCII).
	# Regardless of which sorts first, only one is kept and a warning was emitted.
	assert any("Duplicate skill slug" in record.message for record in caplog.records)


def test_duplicate_slug_first_seen_is_kept(
	tmp_path: Path,
	make_skill: Any,
	caplog: pytest.LogCaptureFixture,
) -> None:
	# Force a known sort order by using clearly ordered folder names.
	make_skill(tmp_path, "a-folder", body="first body", frontmatter={"name": "dup"})
	make_skill(tmp_path, "b-folder", body="second body", frontmatter={"name": "dup"})
	with caplog.at_level(logging.WARNING, logger="skills_mcp"):
		skills = discover_skills([tmp_path], "SKILL.md")
	assert len(skills) == 1
	# rglob sorted lexicographically → a-folder/SKILL.md comes first.
	assert skills[0].folder.name == "a-folder"
	assert "first body" in skills[0].description


def test_multi_root_discovery(tmp_path: Path, make_skill: Any) -> None:
	root_a = tmp_path / "root-a"
	root_b = tmp_path / "root-b"
	root_a.mkdir()
	root_b.mkdir()
	make_skill(root_a, "from-a", body="aa")
	make_skill(root_b, "from-b", body="bb")
	skills = discover_skills([root_a, root_b], "SKILL.md")
	assert {s.slug for s in skills} == {"from_a", "from_b"}


def test_main_file_must_be_a_file_not_dir(tmp_path: Path) -> None:
	# Create a directory literally named SKILL.md — rglob will match it, but the
	# is_file() check should skip it.
	(tmp_path / "weird" / "SKILL.md").mkdir(parents=True)
	assert discover_skills([tmp_path], "SKILL.md") == []
