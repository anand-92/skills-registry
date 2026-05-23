# skills-registry — Website Content Brief

This document is a raw information dump for the website designer. It contains everything currently known about the project. The designer is free to decide what to include, what to drop, how to structure it, and how to present it. No layout, ordering, or visual guidance is implied here — sections below are just topical groupings.

---

## Project identity

- **Name:** `skills-registry`
- **Tagline (one of many possible phrasings):** "One GitHub repo, every AI agent. Skills fetched on demand — not auto-loaded into every startup context."
- **Current version:** 0.5.0 (pre-1.0, day-to-day usable, MCP tool surface and CLI commands are stable; internals may shift between minor versions)
- **License:** Apache-2.0
- **Author / maintainer:** anand-92 (GitHub handle)
- **Project status:** Development Status :: 4 - Beta
- **Languages used:** Python 3.10+ and Go 1.24+

---

## Important links

- **GitHub repository:** https://github.com/anand-92/skills-registry
- **Issues:** https://github.com/anand-92/skills-registry/issues
- **GitHub security advisories:** https://github.com/anand-92/skills-registry/security/advisories/new
- **GitHub releases (Go CLI binaries):** https://github.com/anand-92/skills-registry/releases
- **PyPI package:** `skills-registry` (install via `pip install skills-registry` or `uv tool install skills-registry` or `uvx skills-registry ...`)
- **CI status badge URL:** https://github.com/anand-92/skills-registry/actions/workflows/ci.yml/badge.svg
- **Model Context Protocol (referenced standard):** https://modelcontextprotocol.io
- **FastMCP (underlying Python framework):** https://github.com/jlowin/fastmcp
- **GitHub CLI dependency:** https://cli.github.com/
- **uv (Python package manager dependency):** https://github.com/astral-sh/uv
- **CONTRIBUTING.md:** in the repo root
- **SECURITY.md:** in the repo root
- **AGENTS.md (architecture notes for AI assistants / new contributors):** in the repo root
- **Architecture deep dive doc:** `docs/registry.md` in the repo

---

## The problem the project solves

AI coding tools — Claude Code, Cursor, Codex, Goose, Windsurf, Claude Desktop, VS Code/Copilot, and others — let users author "skills" (markdown files that teach the agent how to do something). Today, those tools each maintain their own local skills folder:

- `~/.claude/skills`
- `~/.cursor/skills`
- `~/.factory/skills`
- `~/.codex/skills`
- …and so on across 50+ known AI tool dot-folders.

Two problems result:

1. **Duplication and drift.** The same skill has to be copy-pasted into each tool's folder, and changes have to be applied N times.
2. **Token bloat.** Every skill in every folder is auto-loaded into the agent's startup context, regardless of whether the user's current task needs it. The user pays for those tokens on every conversation.

`skills-registry` flips the model. Skills live in **one GitHub repository the user owns**. Agents fetch skills on demand through a Model Context Protocol (MCP) server. The only thing each agent auto-loads is a tiny pointer file that teaches it *how* to fetch the rest.

---

## What it actually does (capabilities)

- Stores all of a user's skills in a single GitHub repository they own.
- Exposes that repository over MCP with three tools that any MCP-aware AI client can call: `list_skills`, `get_skill`, `publish_skill`.
- Provides a Charmbracelet-based TUI (`skill-registry`) for manual day-to-day management: list, get, sync, add, publish, bootstrap.
- Auto-detects existing local skills across 50+ known AI tool dot-folders during initial setup and offers to push them into the new registry.
- Writes a single `skill-registry/SKILL.md` pointer file into each selected agent's dot-folder so the agent knows the registry exists and how to query it.
- Caches downloaded skills locally and invalidates the cache automatically when the registry's tree SHA changes.

---

## Benefits / value props (in user-facing language)

- **Lighter agent startup.** A directory of `SKILL.md` files no longer balloons every conversation's context window. Agents pull what they need, when they need it.
- **One home for all skills.** No more keeping `~/.claude/skills`, `~/.cursor/skills`, `~/.factory/skills`, etc. in sync by hand. Edit once, every agent sees the update.
- **Share and version like code.** The registry is a Git repo. Branch it, PR it, fork a teammate's, restore old versions.
- **Works in every MCP client.** Any MCP-compatible AI tool can be wired up to the registry — the bootstrap recognizes 50+ tools by default.
- **No SSH / shell config needed.** All GitHub I/O goes through the user's already-authenticated `gh` CLI. No SSH keys, no `git config user.email`, no credential helpers required.
- **Single source of truth.** Edit a skill once in the registry repo; every agent sees the new version on next fetch.

---

## What is a "skill"?

A skill is a folder containing a `SKILL.md` (Markdown with optional YAML frontmatter) plus any supporting files the agent might need.

Example:

```markdown
---
name: PDF Processing
description: Extract and summarize PDF documents
---

# PDF Processing

When the user asks about a PDF, do the following:
1. Read the file with the pdf-text tool
2. Summarize section by section
...
```

One file, plus whatever reference docs or examples the agent should be able to see. Most modern AI coding tools already understand this format.

---

## How it compares to alternatives

|                                            | Local dot-folders | Dotfiles repo | skills-registry |
|--------------------------------------------|:-----------------:|:-------------:|:---------------:|
| One home for all your agents               | duplicated        | yes           | yes             |
| Fetched on demand (no startup tokens)      | no                | no            | yes             |
| Versioned + branchable                     | no                | yes           | yes             |
| Works in every MCP client                  | partial           | no            | yes             |
| Share / fork between users                 | no                | clunky        | yes (clone repo)|
| No shell or SSH config needed              | yes               | no            | yes             |

---

## Architecture overview

`skills-registry` ships three coordinated deliverables from a single source repo:

| Piece                  | Language    | Distribution                                                   | Role                                                                                                |
|------------------------|-------------|----------------------------------------------------------------|-----------------------------------------------------------------------------------------------------|
| `skills-registry`      | Python 3.10+| PyPI wheel                                                     | Thin bootstrap. Verifies `gh`, downloads the Go CLI, `exec`s it. Single command: `skills-registry init`. |
| `skill-registry-mcp`   | Python 3.10+| Same PyPI wheel, second entry point                            | FastMCP server exposing `list_skills`, `get_skill`, `publish_skill` over MCP stdio.                  |
| `skill-registry`       | Go 1.24+    | GitHub Releases tarballs (darwin/linux/windows × amd64/arm64) | Charmbracelet TUI manager. Commands: `bootstrap`, `list`, `get`, `sync`, `add`, `publish`.            |

Underlying tech:

- Python build: `hatchling` (PEP 517).
- Python runtime dependency: `fastmcp >= 3.1.1, < 4`.
- Python dev tooling: `uv`, `pytest`, `pytest-cov`, `ruff`, `pre-commit`.
- Go TUI: Charmbracelet (`bubbletea`, `lipgloss`, `bubbles`), plus `cobra` for the CLI and `yaml.v3` for frontmatter.
- MCP transport: stdio via FastMCP 3.x.
- Network surface: every GitHub call is made via the `gh api` subprocess. No direct HTTP. No `git` binary. No SSH.

---

## How GitHub I/O works (technical detail)

Because desktop MCP clients (Claude Desktop, Cursor, VS Code/Copilot) spawn the MCP server with a stripped environment — no shell `PATH`, no `SSH_AUTH_SOCK`, no guaranteed `git config user.email` — `skills-registry` deliberately does *not* shell out to `git`, does not use SSH, and does not embed an HTTP client.

Every write goes through the GitHub Git Data API via `gh api`. The publish sequence is:

```
GET   /repos/{owner}/{repo}/git/ref/heads/{branch}        → parent SHA
GET   /repos/{owner}/{repo}/git/commits/{parent}          → base tree SHA
GET   /repos/{owner}/{repo}/git/trees/{base}?recursive=1  → list stale files under <slug>/
POST  /repos/{owner}/{repo}/git/blobs                     → upload each file
POST  /repos/{owner}/{repo}/git/trees                     → assemble new tree
POST  /repos/{owner}/{repo}/git/commits                   → create commit
PATCH /repos/{owner}/{repo}/git/refs/heads/{branch}       → fast-forward ref
```

Conflicts (HTTP 409/422) trigger up to 3 retries with exponential backoff against the freshly-fetched HEAD. The same flow is implemented in both Python (`RegistryClient.publish_skill`) and Go (`registry.Client.Publish`).

---

## Caching

`get_skill` writes downloads to `~/.cache/skills-mcp/skills/<slug>/` with a sibling `<slug>.meta.json` recording the registry tree SHA at fetch time. On the next call:

1. The current tree SHA for `<slug>/` is fetched from GitHub.
2. If it matches the cached meta SHA, the cached folder path is returned immediately.
3. Otherwise the folder is wiped, re-downloaded, and the meta is rewritten.

Cache invalidation is keyed on tree SHA (not ETag or `Last-Modified`), so force-pushes and any subtree change correctly invalidate.

---

## Configuration

| Variable                          | Default                  | Purpose                                                                                                |
|-----------------------------------|--------------------------|--------------------------------------------------------------------------------------------------------|
| `SKILLS_REGISTRY`                 | (from config file)       | Per-process override. Accepts `owner/repo` or `owner/repo@branch`. Useful for browsing a teammate's.   |
| `SKILLS_LOG_LEVEL`                | `INFO`                   | Set to `DEBUG` for verbose troubleshooting.                                                            |
| `XDG_CONFIG_HOME` / `XDG_CACHE_HOME` | OS default            | Where the registry config and skill cache live.                                                        |
| `SKILLS_MAX_FILE_BYTES`           | `2097152` (2 MiB)        | Per-file size cap enforced by `publish_skill` to prevent accidental binary uploads.                    |
| `SKILLS_BIN_DIR`                  | `~/.local/bin`           | Override where the bootstrap installs the Go binary.                                                   |

Persistent config file path: `~/.config/skills-mcp/registry.toml`. Format:

```toml
[registry]
repo = "alice/skill-registry"
default_branch = "main"
```

Resolution order: env var > config file > error.

---

## Prerequisites

- **GitHub CLI (`gh`)** installed and authenticated. Verify with `gh auth status`.
- **uv** (the Python package manager). Install via `pipx install uv` if not present.
- (Optional) Python 3.10+ if invoking via `pip` directly. `uvx` does not require a system Python.

The package is OS-independent in design; CI builds and tests on Linux. The Go CLI ships prebuilt binaries for:

- `darwin/amd64`
- `darwin/arm64`
- `linux/amd64`
- `linux/arm64`
- `windows/amd64`

(Windows support for the bootstrap step is best-effort; the Go binary builds for Windows but `skills-registry init`'s download + `chmod` flow assumes POSIX.)

---

## Installation and first-run setup

The entire installation is one command:

```
uvx skills-registry init
```

What that command does, in order:

1. Verifies that `gh` is installed and authenticated. Exits with code 3 if `gh` is missing, code 4 if it is not authed.
2. Downloads the matching Go binary (`skill-registry`) from the latest GitHub release into `~/.local/bin` (or `$SKILLS_BIN_DIR`).
3. `os.execv`s into the Go binary, handing off to `skill-registry bootstrap`.
4. The Go binary then:
   - Scans the user's AI tool dot-folders for existing skills.
   - Prompts for a registry repo name and visibility (public/private).
   - Creates the GitHub repo via `gh repo create`.
   - Pushes every found skill into the new repo via the Git Data API.
   - Presents a multi-select TUI of detected agents, with universal ones (e.g. `~/.factory`, `~/.codex`) pre-selected.
   - Writes a `skill-registry/SKILL.md` pointer file into each selected agent's skills folder.
   - Saves `~/.config/skills-mcp/registry.toml`.
   - Prints the MCP JSON snippet to paste into the user's MCP client config.

The bootstrap is **idempotent**: re-running detects the existing config and skips repo creation.

To install the MCP server *persistently* (so MCP clients can launch it without depending on the `uvx` cache), the recommended command is:

```
uv tool install skills-registry
```

This installs both console-script entry points (`skills-registry` and `skill-registry-mcp`).

---

## CLI commands (the Go `skill-registry` binary)

| Command                                  | What it does                                                                                            |
|------------------------------------------|---------------------------------------------------------------------------------------------------------|
| `skill-registry bootstrap`               | First-run setup. Idempotent; safe to re-run.                                                            |
| `skill-registry list`                    | Fuzzy-filterable TUI list of every skill in the user's registry.                                        |
| `skill-registry get <slug>`              | Download one skill into `./skill-registry/<slug>/`.                                                     |
| `skill-registry sync`                    | Push local skills sitting in `.claude/skills`, `.cursor/skills`, etc., that are missing from the registry.|
| `skill-registry add <owner/repo>`        | Clone someone else's registry, multi-select which of their skills to pull into the user's own registry. |
| `skill-registry publish <path>`          | Publish a single local skill folder.                                                                    |
| `skill-registry --version`               | Print version.                                                                                          |

The TUI is fuzzy-filterable: press `/` to search, Enter to preview.

---

## MCP tools (exposed by `skill-registry-mcp`)

Three tools exposed via FastMCP over stdio:

- **`list_skills`** — read-only. Enumerates every skill in the user's registry. Returns a markdown table with slug, name, description, and the URI to fetch the skill via `get_skill`.
- **`get_skill(slug)`** — read-only. Downloads a single skill into the local cache and returns the absolute path on disk. The folder contains `SKILL.md` plus any supporting files.
- **`publish_skill(name, files=..., local_folder=...)`** — destructive (writes to GitHub). Publishes a skill to the registry. Accepts either a `files` mapping (path → text content) or `local_folder` (absolute path to a folder containing `SKILL.md`). Returns the new commit SHA.

Users don't typically call these tools directly. The user types things like:

> "What skills do I have available?"
> "Get the `code-review` skill and use it on this PR."

…and the agent calls the tools automatically.

---

## MCP client configuration snippets

### Claude Code / Claude Desktop / Cursor / VS Code (`mcp.json`)

```json
{
  "mcpServers": {
    "skill-registry": {
      "command": "/Users/you/.local/bin/skill-registry-mcp"
    }
  }
}
```

### Codex (`~/.codex/config.toml`)

```toml
[mcp_servers.skill-registry]
command = "/Users/you/.local/bin/skill-registry-mcp"
```

The `skills-registry init` command prints platform-correct JSON automatically. The above are for manual setup.

---

## Supported agent dot-folders (detected at bootstrap)

The Go binary's `cli/internal/agents/agents.go` carries a catalogue of 50+ known AI-tool dot-folders, each annotated with a display name and a "universal" flag. Examples of recognized tools:

- Claude Code (`~/.claude`)
- Claude Desktop
- Cursor (`~/.cursor`)
- Codex (`~/.codex`)
- VS Code / Copilot
- Windsurf
- Goose
- Factory (`~/.factory`)

…among others. The full list lives in `cli/internal/agents/agents.go` and is treated as the single source of truth.

---

## Security model and threat surface

- No `git` shell-out, no SSH agent dependency, no embedded HTTP client. All GitHub I/O routes through the user's authenticated `gh` CLI. `gh auth status` is the only trust anchor.
- `subprocess.run()` is used with list args only (never `shell=True`).
- `publish_skill` rejects paths containing `..` segments. Dotfiles (`.git`, `.DS_Store`, etc.) and `__pycache__` are skipped.
- Path normalization rejects backslash-encoded traversals and absolute-path injection.
- Per-file size cap (`SKILLS_MAX_FILE_BYTES`, default 2 MiB) prevents accidental upload of huge binaries.
- The Go binary uses identical validation paths.
- Frontmatter parsing is intentionally minimal (no real YAML deserializer) to avoid YAML-related CVEs.

Out of scope: model-side risks (jailbreaks, prompt injection in skill content). Skills are user-controlled prompts and should be treated with the same care as any other prompt.

Vulnerability reports should be sent **privately** via GitHub Security Advisories: https://github.com/anand-92/skills-registry/security/advisories/new

---

## Troubleshooting reference

- **`gh not found` or exit code 3.** Install GitHub CLI from https://cli.github.com/ and run `gh auth login`. `gh` must be on `PATH` or in one of: `~/.local/bin`, `/opt/homebrew/bin`, `/usr/local/bin`, `/usr/bin`.
- **Exit code 4 (`gh auth status` failed).** Run `gh auth login`.
- **Exit code 5 (couldn't fetch the Go binary).** Download manually from the releases page and drop into `~/.local/bin/skill-registry`.
- **"No registry configured."** Run `skills-registry init`, or set `SKILLS_REGISTRY=owner/repo` directly.
- **MCP server doesn't show up in the client.** Confirm the JSON snippet was pasted (the absolute path to `skill-registry-mcp` matters; desktop MCP clients don't inherit shell `PATH`). Fully restart the client (not just reload).
- **Multiple GitHub accounts.** `skills-registry` uses whichever account `gh auth status` says is active. Use `gh auth switch` before `init` to pick the right one.
- **`publish_skill` keeps returning conflicts.** Another publish (CLI or MCP) is racing. Retry budget is 3.
- **Cache never invalidates.** Inspect `~/.cache/skills-mcp/skills/<slug>.meta.json`; its `tree_sha` must equal the GitHub-reported folder SHA.

---

## Example end-user workflows

### First-time setup

```bash
uvx skills-registry init
# Follow prompts (repo name, visibility, agent multi-select)
# Paste the printed MCP JSON snippet into the MCP client config
# Restart the MCP client
```

### Ask an agent about available skills

> *"What skills do I have available?"*

The agent calls `list_skills` and shows the user a table.

### Use a skill on a task

> *"Get the `code-review` skill and use it on this PR."*

The agent calls `get_skill("code-review")`, reads the returned files, and follows the instructions.

### Publish a new skill from a local folder

```bash
skill-registry publish ./my-new-skill
```

### Pull a skill from another user's public registry

```bash
SKILLS_REGISTRY=other-user/their-registry skill-registry list
skill-registry add other-user/their-registry
```

### Sync skills authored in local agent folders

```bash
skill-registry sync
```

---

## Development and contribution information

- Source repo: https://github.com/anand-92/skills-registry
- Issue tracker: https://github.com/anand-92/skills-registry/issues
- Contribution guide: `CONTRIBUTING.md` in repo
- Architecture deep dive: `docs/registry.md` in repo
- Agent / new-contributor notes: `AGENTS.md` in repo

Local development:

```bash
git clone https://github.com/anand-92/skills-registry
cd skills-mcp
uv sync --group dev

# Python tests
uv run pytest -v --cov=skills_mcp --cov-report=term-missing

# Go tests
(cd cli && go vet ./... && go test ./...)

# Lint / format
uv run ruff check .
uv run ruff format .

# Pre-commit
uv run pre-commit install

# Local smoke test of the Go binary
(cd cli && go build -o /tmp/skill-registry ./cmd/skill-registry && /tmp/skill-registry --help)
```

Test counts at time of writing: 139 Python tests via pytest, plus Go tests for `agents`, `bootstrap`, `config`, `scan`, `registry`.

CI / CD:

- `.github/workflows/ci.yml` — Python (ruff + pytest with coverage) and Go (vet + build + test) matrix; runs on every push/PR.
- `.github/workflows/release.yml` — publishes the Python wheel to PyPI on `release: published`.
- `.github/workflows/release-cli.yml` — on `cli-v*` tag push, builds the cross-platform tarballs (darwin/amd64, darwin/arm64, linux/amd64, linux/arm64, windows/amd64) and uploads them as release assets. `skills-registry init` downloads from this same release.

Commit message style: conventional-commits-ish (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).

---

## Roadmap / known gaps (current as of v0.5.0)

- No `remove` or `update` CLI commands (the underlying publish flow already handles deletes via stale-file detection; user-facing surface is the missing piece).
- No multi-registry support — config is one repo at a time. A `[registries]` array and a `connect <owner/repo>` command would enable side-by-side registries.
- Browsing third-party public registries (read-only) is possible via `SKILLS_REGISTRY=owner/repo` but isn't yet a first-class flow.
- Windows bootstrap path is best-effort (POSIX assumptions in download + chmod).
- The `SKILL.md` template is duplicated between Python (`skill_md.py`) and Go (`bootstrap/skillmd.go`); they must stay in sync.
- The frontmatter parser is "YAML-ish" — multi-line values, lists, and nested keys are silently dropped. Sufficient for current scope.
- No PR-based contribution flow to upstream registries yet (would lean on `gh api` for the fork+PR dance).

---

## Glossary

- **MCP (Model Context Protocol):** an open protocol for connecting AI clients to external tools and data sources. See https://modelcontextprotocol.io
- **FastMCP:** the Python framework used to implement the MCP server. See https://github.com/jlowin/fastmcp
- **Skill:** a folder containing a `SKILL.md` plus any supporting files; defines a reusable instruction set for an AI agent.
- **Registry:** the user's GitHub repository holding all of their skills.
- **Slug:** the URL-safe, lowercased identifier for a skill, derived from its name.
- **Bootstrap:** the first-run setup flow that creates the registry repo and wires up agents.
- **Dot-folder:** the hidden directory each AI tool uses to store skills (e.g. `~/.claude`, `~/.cursor`, `~/.factory`).
- **Tree SHA:** GitHub's content-addressed identifier for a folder; used as the cache invalidation key.

---

## Tone notes (for copy)

- The project is technical but the audience includes both developers and AI-tool power users.
- Existing copy in the README uses casual-but-precise phrasing ("you get…", "that's the whole install", "branch it, PR it, fork your teammate's"). Friendly, no jargon-for-jargon's-sake.
- The product is **honest about being pre-1.0**: stable surface, but internals may shift. This should not be hidden.
- The project is opinionated about one technical choice in particular: every GitHub call goes through `gh`. This is a deliberate robustness decision (GUI MCP clients don't inherit shell environments) and is worth surfacing if it fits.

---

## Calls to action that already exist

- "Install: `uvx skills-registry init`"
- "Star the repo: https://github.com/anand-92/skills-registry"
- "Report a bug / request a feature: https://github.com/anand-92/skills-registry/issues"
- "Read the contributing guide: `CONTRIBUTING.md`"
- "View the architecture deep dive: `docs/registry.md`"
