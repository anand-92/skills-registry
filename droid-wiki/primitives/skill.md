# Skill

Active contributors: Nik Anand

## What a skill is

A **skill** is a folder. The folder must contain a file named `SKILL.md` at its root. Everything else — scripts, assets, resources, supporting markdown — is optional. The folder is the unit of distribution: a publish replaces the whole folder, a download fetches the whole folder, a remove deletes the whole folder.

`SKILL.md` is the dispatcher. An agent that downloads a skill via `get_skill` is contracted to read `SKILL.md` first and only load the supporting files the dispatcher tells it to. Loading everything unconditionally would waste tokens; structuring SKILL.md as a router gives skill authors fine-grained control over the model's working memory.

## The in-memory shape

Two implementations, one contract:

| Language | Type | File |
| --- | --- | --- |
| Python | `SkillSummary(slug, name, description, path, tree_sha)` | `src/skills_mcp/registry_api.py` |
| Go | `scan.Skill{Slug, Name, Description, Folder, Source}` (local) and `registry.Summary{Slug, Name, Description, TreeSHA}` (remote) | `cli/internal/scan/scan.go`, `cli/internal/registry/registry.go` |

Both languages frame "skill" as five-or-fewer fields:

- **Slug** — the canonical filesystem-safe identifier.
- **Name** — the human display name (read from frontmatter, falls back to the folder basename).
- **Description** — one short paragraph (read from frontmatter, falls back to the first non-heading paragraph of the body, capped at 240/300 characters).
- **Folder / Path / TreeSHA** — where the skill lives; the registry's tree SHA when the record came from a `gh api` response.
- **Source** (Go local only) — the human label of the discovery root (`~/.claude/skills`, `.agents/skills`, …) so the wizard's multi-select can show which dot-folder a candidate came from.

`scan.Skill` additionally exposes a `Hash() (string, error)` method that returns the SHA-256 of the on-disk `SKILL.md`. Used by content-aware dedupe when the same slug shows up in multiple dot-folders — see [../systems/agent-catalogue.md](../systems/agent-catalogue.md).

## Slugify

Slugs are the registry's canonical identifier. Two implementations, identical algorithm:

```python
# src/skills_mcp/registry_api.py
_SLUG_RE = re.compile(r"[^a-z0-9]+")

def slugify(name: str) -> str:
    return _SLUG_RE.sub("_", name.strip().lower()).strip("_") or "skill"
```

```go
// cli/internal/scan/scan.go
var slugRe = regexp.MustCompile(`[^a-z0-9]+`)

func Slugify(name string) string {
    s := slugRe.ReplaceAllString(strings.ToLower(strings.TrimSpace(name)), "_")
    s = strings.Trim(s, "_")
    if s == "" {
        return "skill"
    }
    return s
}
```

In English:

1. Lowercase.
2. Replace every run of non-`[a-z0-9]` characters with a single underscore.
3. Strip leading and trailing underscores.
4. Empty result falls back to the literal `"skill"`.

So `"AGP-9 Upgrade"` → `"agp_9_upgrade"`. So does `"agp_9_upgrade"`. So does `"   AGP_9-Upgrade   "`. The function is idempotent (`Slugify(Slugify(x)) == Slugify(x)` for any input) and produces the same result on either side of the language boundary — the slug a Python publish produces is byte-identical to what a Go discovery would compute for the same display name.

The CLI exploits this to handle a real-world ambiguity: agent dot-folders often contain skills whose folder names use hyphens (`agp-9-upgrade`), but the registry stores them under the canonical slug (`agp_9_upgrade`). Both the `get` destination resolver (`resolveDest`) and the `remove` dot-folder sweep (`matchSlugChildren`) match by literal name OR `Slugify(name)` to keep the two namespaces from drifting.

## Frontmatter

The optional YAML-ish block at the top of `SKILL.md` carries two keys we read:

```markdown
---
name: Auth skill
description: Validates JWT signatures against your KMS-managed keypair.
---

# Auth skill

This skill knows how to …
```

Both parsers (`src/skills_mcp/frontmatter.py` and the inline parser in `cli/internal/scan/scan.go`) are YAML-ish, not full YAML. The Go side uses `gopkg.in/yaml.v3` to parse the block but flattens nested values into strings; the Python side hand-rolls a key/value loop. The supported shape is one-level scalar keys: `name`, `description` plus anything else a skill author wants to add (we ignore unrecognized keys). Multi-line values, nested keys, and explicit lists are silently collapsed or dropped.

When frontmatter is missing or doesn't carry `name`, the registry falls back to the folder basename (`filepath.Base(folder)`). When `description` is missing, both implementations fall back to the first non-heading paragraph of the body, capped (240 chars in Go, 300 in Python). When everything is empty, the Go side emits `"Skill: <name>"` as a last resort.

## Per-file size cap

A skill folder is bounded by `SKILLS_MAX_FILE_BYTES` (default `2 * 1024 * 1024` = 2 MiB) **per file**. There is no folder-total cap. The cap is enforced in two places:

- Python: `registry_server._validate_size(payload)` raises `ValueError` listing the offending path and byte count before the publish call goes out.
- Go: `publish.go:collectFiles` skips oversized files with a stderr warning. `bootstrap.go:walkSkillIntoFiles` does the same in the bulk-import path.

The cap is intentionally generous for text (a 2 MiB SKILL.md is a manifesto) and intentionally tight for binaries (a 2 MiB PNG is probably a mistake). Override with the `SKILLS_MAX_FILE_BYTES` env var if you have a legitimate need.

## Path validation

A publish payload's keys are run through `_normalize_rel_path` (Python) / equivalent inline checks (Go) before any blob upload. Three protections layered together:

1. `os.sep → /` so backslash-encoded Windows-style traversals can't sneak through.
2. Leading `./` stripped iteratively so `././../etc` normalizes to `../etc` (and then gets rejected).
3. Leading `/` stripped so absolute-path injection (`"/etc/passwd"`) collapses to `"etc/passwd"`.
4. After splitting on `/`, any segment equal to `..` is rejected outright with a `ValueError`.

Hidden entries (any path component starting with `.`) and `__pycache__` are filtered out of the local-folder walker before the cap check even runs — `.git/`, `.DS_Store`, build caches, and editor swap files never reach the registry.

## What a skill is not

- **Not versioned.** The registry's idea of "what's the current version" is "what's at HEAD of the default branch". Force-pushes overwrite. A skill author who wants stable versions should publish under multiple slugs (`my-skill-v1`, `my-skill-v2`).
- **Not namespaced.** Two skills with the same slug collide. The registry is a flat namespace by design — the slug is the only identity. The CLI's `add` flow does collision detection (`scan.DedupeAgainst`) and refuses to overwrite without explicit confirmation.
- **Not discoverable without `gh`.** Reading the registry requires an authenticated `gh`. We don't expose a public HTTP surface; the registry is meant to be your registry.

## Key source files

| File | Role |
| --- | --- |
| `src/skills_mcp/registry_api.py` | `slugify`, `SkillSummary`, `_parse_skill_md`. |
| `src/skills_mcp/frontmatter.py` | `parse_frontmatter` + `first_paragraph`. |
| `cli/internal/scan/scan.go` | `Slugify`, `Skill`, `Hash`, `Discover`, `parseFrontmatter`, `firstParagraph`. |
| `cli/internal/registry/registry.go` | `Summary`, the on-the-wire mirror used by `client.List`. |

## Cross-references

- [../systems/registry-client.md](../systems/registry-client.md) — how `SkillSummary` / `Summary` is constructed from `gh api` responses.
- [../api/mcp-tools.md](../api/mcp-tools.md) — the three tools that consume the slug.
- [../api/cli-commands.md](../api/cli-commands.md) — the subcommands that use Slugify for destination resolution and dot-folder cleanup.
- [../systems/caching.md](../systems/caching.md) — how a slug becomes a cache path.
- [registry-config.md](registry-config.md) — the other primitive every operation depends on.
