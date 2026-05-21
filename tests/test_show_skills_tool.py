"""Tests for the consolidated ``show_skills`` tool."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from skills_mcp.__main__ import build_server


@pytest.fixture
def event_loop():
	loop = asyncio.new_event_loop()
	yield loop
	loop.close()


def test_single_show_skills_tool_registered(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
	make_skill: Any,
) -> None:
	make_skill(tmp_path, "alpha", body="Alpha body.", frontmatter={"name": "Alpha"})
	make_skill(tmp_path, "bravo", body="Bravo body.", frontmatter={"name": "Bravo"})
	monkeypatch.setenv("SKILLS_ROOT", str(tmp_path))

	mcp = build_server()
	tools = asyncio.run(mcp.list_tools())

	names = [t.name for t in tools]
	assert names == ["show_skills"]


def test_show_skills_output_contains_all_skills(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
	make_skill: Any,
) -> None:
	make_skill(tmp_path, "alpha", body="Alpha body.", frontmatter={"name": "Alpha"})
	make_skill(tmp_path, "bravo", body="Bravo body.", frontmatter={"name": "Bravo"})
	monkeypatch.setenv("SKILLS_ROOT", str(tmp_path))

	mcp = build_server()
	result = asyncio.run(mcp.call_tool("show_skills", {}))

	text = ""
	for item in result:
		text += item.text if hasattr(item, "text") else str(item)

	assert "alpha" in text
	assert "bravo" in text
	assert "Skills:" in text
	assert str(tmp_path) in text


def test_show_skills_returns_no_skills_message_when_empty(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	monkeypatch.setenv("SKILLS_ROOT", str(tmp_path))

	mcp = build_server()
	result = asyncio.run(mcp.call_tool("show_skills", {}))

	text = ""
	for item in result:
		text += item.text if hasattr(item, "text") else str(item)

	assert "No skills found" in text


def test_no_per_skill_tools_registered(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
	make_skill: Any,
) -> None:
	make_skill(tmp_path, "code-review", body="Review code.", frontmatter={"name": "Code Review"})
	monkeypatch.setenv("SKILLS_ROOT", str(tmp_path))

	mcp = build_server()
	tools = asyncio.run(mcp.list_tools())

	names = [t.name for t in tools]
	assert "skill_code_review" not in names
	assert "show_skills" in names
