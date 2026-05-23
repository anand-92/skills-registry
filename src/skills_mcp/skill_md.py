"""Render the generated ``skill-registry/SKILL.md`` doc-skill.

Written into every dot-folder the user picks during ``init`` so each AI
agent gets a tiny instruction sheet teaching it to fetch skills on demand
instead of pre-loading them.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillMdContext:
	"""Substitution values for the template."""

	registry_repo: str  # "owner/repo"


_TEMPLATE = """---
name: skill-registry
description: |
  Broker to your GitHub-hosted personal skill library at {registry_repo}. Use
  when the user asks for a skill, mentions installing/sharing skills, says
  'use the X skill', or you need specialized domain instructions not already
  loaded in this session.
---

# Skill Registry

Skills are stored at https://github.com/{registry_repo} and fetched on demand
through the `skill-registry-mcp` MCP server (preferred) or the
`skill-registry` CLI (fallback). **Do not assume any skill is already
loaded** — always discover, then fetch, then read.

## 1. Discover what's available

MCP: call the `list_skills` tool.
CLI: `skill-registry list`

Returns a table of slug, name, and one-line description. Match the user's
request against descriptions, not just slugs.

## 2. Fetch the skill

MCP: call `get_skill(slug="<slug>")`. It returns an absolute path to a
cached local folder containing the skill's `SKILL.md` and every supporting
file. **Read every file in that folder** before acting on the skill.

CLI: `skill-registry get <slug> [--dest PATH]`. Same behavior; the command
prints the destination path on stdout.

## 3. Publish a new or updated skill

MCP: `publish_skill(name="<name>", files={{...}})` to upload from memory, or
`publish_skill(local_folder="<path>")` to upload a folder on disk.

CLI:
- `skill-registry publish <path>` — single-skill push from a local folder
- `skill-registry add <source>` — pull from a path, `owner/repo`, or git URL,
  then push selections to the registry
- `skill-registry sync` — scan your AI tool dot-folders for skills not yet in
  the registry; multi-select what to push

## Notes
- All operations require `gh` CLI to be authenticated (`gh auth status`).
- Cached skills live at `~/.cache/skills-mcp/skills/<slug>/`. They're
  refreshed automatically when the upstream tree changes.
"""


def render(ctx: SkillMdContext) -> str:
	"""Return the fully rendered SKILL.md body."""
	return _TEMPLATE.format(registry_repo=ctx.registry_repo)
