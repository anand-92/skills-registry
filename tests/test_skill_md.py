"""Tests for ``skills_mcp.skill_md``."""

from __future__ import annotations

from skills_mcp.skill_md import SkillMdContext, render


def test_render_substitutes_repo() -> None:
	body = render(SkillMdContext(registry_repo="alice/skills"))
	assert "alice/skills" in body
	# Header frontmatter must be present.
	assert body.startswith("---\n")
	assert "name: skill-registry" in body
	# Both MCP and CLI flavors are documented.
	assert "list_skills" in body
	assert "skill-registry list" in body
	assert "get_skill" in body
	assert "skill-registry get" in body
	assert "publish_skill" in body
	assert "skill-registry publish" in body
	# Sync/add commands are documented.
	assert "skill-registry sync" in body
	assert "skill-registry add" in body


def test_render_is_deterministic() -> None:
	a = render(SkillMdContext(registry_repo="x/y"))
	b = render(SkillMdContext(registry_repo="x/y"))
	assert a == b
