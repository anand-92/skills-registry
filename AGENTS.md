# Agent Notes — skills-mcp

This file is a living guide for AI agents and new contributors. It captures the architecture, patterns, and trade-offs of the current (0.3.x) **GitHub-backed registry** design.

> **What changed in 0.3.0:** The project pivoted from "consolidate local skills" (gather/add) to "personal GitHub registry repo, fetched on demand". `gather` and `add` were removed. A new Go CLI handles all interactive UX, and a separate Python MCP server exposes the registry as three tools.

---

## Project Overview

`skills-mcp` is now three coordinated deliverables shipped from a single repo:

| Piece | Language | Distribution | Job |
|---|---|---|---|
| `skills-mcp` (Python) | Python 3.10+ | PyPI (`pip install skills-mcp` / `uvx`) | Thin bootstrap (`skills-mcp init`) + legacy local-folder server (`serve`/`list`). |
| `skill-registry-mcp` (Python) | Python 3.10+ | Same wheel, second `[project.scripts]` entry point | FastMCP server with 3 tools (`list_skills`, `get_skill`, `publish_skill`). |
| `skill-registry` (Go) | Go 1.22+ | GitHub Releases tarballs (built by `.github/workflows/release-cli.yml`) | Charmbracelet TUI: `bootstrap`, `list`, `get`, `sync`, `add`, `publish`. |

- **Build (Python):** `hatchling` (PEP 517)
- **Package manager (Python):** `uv`
- **Test runner (Python):** `pytest` with `pytest-cov`
- **Lint/Format (Python):** `ruff`
- **Build/Test (Go):** stdlib (`go build`, `go test`, `go vet`)
- **TUI library:** Charmbracelet (bubbletea + lipgloss + bubbles + cobra)
- **MCP transport:** stdio via FastMCP 3.x
- **Network surface:** Everything talks to GitHub through `gh api` subprocess calls. **No direct HTTP, no `git` binary, no SSH.**

---

## Repository Layout

```
src/skills_mcp/
  __init__.py            # __version__ = "0.3.0"
  __main__.py            # Legacy local-folder server (serve/list) + init subparser wiring
  init.py                # `skills-mcp init` — thin bootstrap: gh check + Go binary download + os.execv
  registry_server.py     # `skill-registry-mcp` — FastMCP with list_skills / get_skill / publish_skill
  registry_api.py        # RegistryClient: gh-api wrapper, atomic Git-Data-API publish with retry
  gh.py                  # find_gh() PATH+fallback lookup, ensure_authed(), gh_api() helper
  config.py              # ~/.config/skills-mcp/registry.toml read/save + SKILLS_REGISTRY env override
  cache.py               # ~/.cache/skills-mcp/skills/<slug>/ with tree-SHA meta files
  skill_md.py            # Generated `skill-registry/SKILL.md` template renderer

cli/                     # Separate Go module (own go.mod)
  cmd/skill-registry/    # Cobra root + bootstrap/list/get/sync/add/publish commands
  internal/
    agents/              # 53-entry KNOWN_DOT_DIRS catalogue with display names + universal flag
    bootstrap/           # SkillMd renderer + InstallSkillMd + MCP/Codex JSON/TOML snippet builders
    config/              # Go mirror of Python config.py (TOML round-trip)
    registry/            # Go mirror of registry_api.py (gh-api client, atomic Publish, conflict retry)
    scan/                # Dot-folder discovery + frontmatter parsing (Go port of discover_skills)
    tui/                 # Bubble Tea models: list, multi-select, input, choice

tests/                   # 136 Python tests (pytest)
docs/
  registry.md            # Architecture deep dive
.github/workflows/
  ci.yml                 # Python (lint/format/test) + Go (vet/build/test) matrix
  release.yml            # PyPI publish on `release: published`
  release-cli.yml        # Build + upload Go binaries on `cli-v*` tag push
```

---

## Architecture

### Three deliverables, one repo

```
[user] → uvx skills-mcp init (Python)
            ├─ ensure_authed(gh)
            ├─ uv tool install skills-mcp (persists `skill-registry-mcp`)
            ├─ gh release download skill-registry (Go binary → ~/.local/bin)
            └─ os.execv → `skill-registry bootstrap`
                            ├─ scan dot-folders (Go)
                            ├─ prompt name/visibility (Bubble Tea)
                            ├─ gh repo create
                            ├─ Git-Data-API push (blobs → tree → commit → ref)
                            ├─ multi-select agent install targets
                            ├─ write skill-registry/SKILL.md to each
                            └─ print MCP JSON snippet
```

### Why a separate Go binary?

The user-facing `building-glamorous-tuis` skill recommends Charmbracelet (Go). Charmbracelet has no first-class Python equivalent. Building the bootstrap UX in Bubble Tea required a Go binary regardless, so `skills-mcp init` was reduced to **a thin Python shim that downloads-then-execs**. This keeps the polished TUI logic in one place and lets the MCP server stay in Python (where FastMCP lives).

### Why no `git`, no SSH, no HTTP client?

Desktop MCP clients (Claude Desktop, Cursor, VS Code/Copilot) spawn the MCP server with a stripped environment:
- `PATH` doesn't include your shell extensions.
- `SSH_AUTH_SOCK` is unset.
- `git config user.email` may be missing.

To stay robust in those conditions, **every write goes through the GitHub Git Data API**, called via `gh api` (which we've already verified is authed). The sequence is identical in Python (`registry_api.RegistryClient.publish_skill`) and Go (`registry.Client.Publish`):

```
GET  /repos/{r}/git/ref/heads/{branch}        → parent SHA
GET  /repos/{r}/git/commits/{parent}          → base tree SHA
GET  /repos/{r}/git/trees/{base}?recursive=1  → list stale files under <slug>/
POST /repos/{r}/git/blobs                     → upload each file
POST /repos/{r}/git/trees                     → new tree referencing base + blobs (+ null SHAs for deletions)
POST /repos/{r}/git/commits                   → commit pointing at new tree, parents=[parent]
PATCH /repos/{r}/git/refs/heads/{branch}      → fast-forward ref
```

Conflicts (409/422) trigger up to 3 retries with exponential backoff against the freshly-fetched HEAD.

### Caching

`get_skill` writes to `~/.cache/skills-mcp/skills/<slug>/` with a sibling `<slug>.meta.json` storing the **registry tree SHA** at fetch time. The next call:
1. Asks the registry for the current `<slug>/` tree SHA.
2. Returns the cached path immediately if the SHA matches.
3. Otherwise wipes the folder and re-downloads.

Force-pushes and any subtree change correctly invalidate.

### Single source of truth for agent dot-folders

`cli/internal/agents/agents.go` holds the canonical 53-entry list of known AI tool dot-folders, each annotated with a display name and a `Universal`/`UnderHome` flag. The Python side doesn't need this list any more (the legacy `gather` command was the only consumer); for the new flow it's Go-only.

---

## Key Symbols

| Symbol | File | Role |
|---|---|---|
| `RegistryClient` | `src/skills_mcp/registry_api.py` | Python: `list_skills` / `download_skill` / `publish_skill`. Owns Git Data API logic + retry. |
| `registry.Client` | `cli/internal/registry/registry.go` | Go mirror of `RegistryClient`. Same endpoints, same order, same retries. |
| `build_server()` | `src/skills_mcp/registry_server.py` | Constructs the FastMCP server. Validates auth + config at boot. |
| `cmd_init` | `src/skills_mcp/init.py` | Thin bootstrap; `os.execv` into Go binary; no TUI. |
| `runBootstrap` | `cli/cmd/skill-registry/bootstrap.go` | Owns the interactive flow (TUI prompts + repo create + agent multi-select). |
| `find_gh` / `FindGH` | `src/skills_mcp/gh.py`, `cli/internal/registry/registry.go` | PATH + fallback lookup (`~/.local/bin`, `/opt/homebrew/bin`, `/usr/local/bin`, `/usr/bin`). |
| `MultiSelectModel` | `cli/internal/tui/multiselect.go` | Fuzzy-searchable multi-select with locked-universal section. |
| `Skill` / `discover_skills` | `src/skills_mcp/__main__.py` | Still used by the legacy `serve`/`list` path. Slug + frontmatter logic. |
| `scan.Discover` | `cli/internal/scan/scan.go` | Go port of `discover_skills`. Used by `sync`, `add`, `bootstrap`. |

---

## Testing

- **Python:** 136 tests, all passing. Modules covered: `cache`, `config`, `gh`, `init`, `registry_api`, `registry_server`, `skill_md`, plus the original `Skill`/`discover_skills`/frontmatter/slug/cli tests. The `registry_api` suite stubs `gh` with a Python shim that replays scripted JSON responses based on argv substring matches.
- **Go:** Tests for `agents`, `bootstrap`, `config`, `scan`, and `registry` (also uses a `gh` shim invoked via `/bin/sh` → `python3`). Run with `cd cli && go test ./...`.
- Run everything:
  ```bash
  uv run pytest -v --cov=skills_mcp --cov-report=term-missing
  (cd cli && go vet ./... && go test ./...)
  ```

---

## Known Issues & Improvement Opportunities

### Outstanding

1. **No `remove`/`update` commands.** `Publish` already handles deletions via stale-file detection, but there's no user-facing way to drop a skill from the registry. Easy follow-up.
2. **No multi-registry support.** Config is one-repo. Adding a `[registries]` array + a `connect <owner/repo>` CLI command would let an agent see several registries side-by-side.
3. **Browsing third-party public registries** is not yet a first-class flow. The read tools (`list_skills`, `get_skill`) don't require write access — wiring them to an arbitrary `owner/repo` would be a few lines.
4. **Windows MCP-server-side init path** is best-effort. The Go binary builds for Windows, but `skills-mcp init`'s `gh release download` + `chmod` assumes POSIX. PowerShell helpers + `gh.exe` lookup would close this gap.
5. **Skill MD template duplicated** between Python (`skill_md.py`) and Go (`bootstrap/skillmd.go`). They must stay in sync; future template changes should land in both places (and there's no test today that enforces parity).
6. **`build_server()` does no schema validation** of the SKILL.md it serves. A malformed skill makes `list_skills` skip it silently; a verbose-mode error log would help debugging.

### Carried over from the previous design

- **Frontmatter parser is YAML-ish.** Both Python and Go avoid a real YAML dep; multi-line values, lists, and nested keys are silently dropped. Fine for the current scope.

---

## CI / CD

- `.github/workflows/ci.yml` — runs the Python job (ruff lint + format + pytest with coverage) **and** the Go job (vet + build + test) in parallel on every push/PR. Both must be green to merge.
- `.github/workflows/release.yml` — builds and publishes the Python wheel to PyPI on `release: published`. Relies on CI having passed on `main`.
- `.github/workflows/release-cli.yml` — on `cli-v*` tag push, builds `darwin/amd64`, `darwin/arm64`, `linux/amd64`, `linux/arm64`, `windows/amd64` tarballs and uploads them as release assets. `skills-mcp init` downloads from this same release.
- **Gaps:** No Python version matrix yet, no OS matrix for the Python tests, no Dependabot, no codecov upload (coverage XML is generated but not uploaded), no integration tests that actually call GitHub.

---

## Security Notes

- **No `git` shell-out, no SSH agent dependency, no embedded HTTP client.** All GitHub I/O routes through the user's authenticated `gh` CLI.
- `subprocess.run()` is used with list args (no `shell=True`).
- `RegistryClient.publish_skill` rejects paths containing `..` segments and skips dotfiles (`.git`, `.DS_Store`, …) and `__pycache__`.
- `_normalize_rel_path` rejects backslash-encoded traversals and absolute-path injection.
- A per-file size cap (`SKILLS_MAX_FILE_BYTES`, default 2 MiB) prevents accidental upload of huge binaries.
- The Go binary uses identical validation paths.

---

## How to Work on This Repo

```bash
# Setup
uv sync --group dev
(cd cli && go mod download)

# Run all tests (Python + Go)
uv run pytest -v --cov=skills_mcp --cov-report=term-missing
(cd cli && go vet ./... && go test ./...)

# Lint & format Python
uv run ruff check .
uv run ruff format .

# Install pre-commit hooks
uv run pre-commit install

# Smoke-test the Go binary locally
(cd cli && go build -o /tmp/skill-registry ./cmd/skill-registry && /tmp/skill-registry --help)
```

When making changes:
- **Keep Python and Go in sync.** If you change the registry contract (`registry_api.py` ↔ `registry.go`), update both implementations and both test suites in the same PR. Same for the `skill-registry/SKILL.md` template.
- Do not add new mandatory runtime dependencies without justification. The Python side has exactly one (`fastmcp`); the Go side has cobra + bubbletea/bubbles/lipgloss + yaml.v3.
- Update `README.md` and `docs/registry.md` if you change anything user-visible.
- Add or update tests for any behavior change. Untested behavior is treated as undefined.
- Use conventional-commit prefixes (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).
- **GUI environment safety:** any new code that talks to GitHub MUST go through `gh api` (or `gh release download` / `gh repo create`). Never assume `git`, `ssh`, or `user.name`/`user.email` are configured.
