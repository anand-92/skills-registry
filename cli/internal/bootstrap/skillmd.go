// Package bootstrap orchestrates the one-time setup flow (gh check, repo
// create, agent multi-select) and the supporting helpers (SKILL.md
// rendering, dot-folder install).
package bootstrap

import "fmt"

// SkillMd returns the body of the generated skill-registry/SKILL.md.
// Kept in sync with skills_mcp.skill_md.render().
func SkillMd(registryRepo string) string {
	return fmt.Sprintf(skillMdTemplate, registryRepo, registryRepo)
}

const skillMdTemplate = `---
name: skill-registry
description: |
  Broker to your GitHub-hosted personal skill library at %s. Use
  when the user asks for a skill, mentions installing/sharing skills, says
  'use the X skill', or you need specialized domain instructions not already
  loaded in this session.
---

# Skill Registry

Skills are stored at https://github.com/%s and fetched on demand
through the ` + "`skill-registry-mcp`" + ` MCP server (preferred) or the
` + "`skill-registry`" + ` CLI (fallback). **Do not assume any skill is already
loaded** — always discover, then fetch, then read.

## 1. Discover what's available

MCP: call the ` + "`list_skills`" + ` tool.
CLI: ` + "`skill-registry list`" + `

Returns a table of slug, name, and one-line description. Match the user's
request against descriptions, not just slugs.

## 2. Fetch the skill

MCP: call ` + "`get_skill(slug=\"<slug>\")`" + `. It returns an absolute path to a
cached local folder containing the skill's ` + "`SKILL.md`" + ` and every supporting
file. **Read every file in that folder** before acting on the skill.

CLI: ` + "`skill-registry get <slug> [--dest PATH]`" + `. Same behavior; the command
prints the destination path on stdout.

## 3. Publish a new or updated skill

MCP: ` + "`publish_skill(name=\"<name>\", files={...})`" + ` to upload from memory, or
` + "`publish_skill(local_folder=\"<path>\")`" + ` to upload a folder on disk.

CLI:
- ` + "`skill-registry publish <path>`" + ` — single-skill push from a local folder
- ` + "`skill-registry add <source>`" + ` — pull from a path, ` + "`owner/repo`" + `, or git URL,
  then push selections to the registry
- ` + "`skill-registry sync`" + ` — scan your AI tool dot-folders for skills not yet in
  the registry; multi-select what to push

## Notes
- All operations require ` + "`gh`" + ` CLI to be authenticated (` + "`gh auth status`" + `).
- Cached skills live at ` + "`~/.cache/skills-mcp/skills/<slug>/`" + `. They're
  refreshed automatically when the upstream tree changes.
`
