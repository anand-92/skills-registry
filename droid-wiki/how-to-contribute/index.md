# How to contribute

`skills-registry` is small, focused, and written to stay that way. The MCP server has exactly one mandatory runtime dependency (`fastmcp`); the Go CLI runs on cobra plus the Charmbracelet stack and `yaml.v3`. Pages in this section explain how to land a change without growing that surface.

## Project ethos

- **Small and focused.** Two deliverables, one shared contract, one user-visible flow. New features need to justify their own weight.
- **No magic.** Bootstrap shells out to `git push`; everything else routes through `gh api`. There is no embedded HTTP client, no SSH agent, no shell expansion. If a behaviour is surprising, it's a bug.
- **Backwards-compatible by default.** The MCP tool surface (`list_skills`, `get_skill`, `publish_skill`) and the CLI subcommands are considered stable. Breaking either requires a minor version bump and a `BREAKING CHANGE:` footer on the commit.
- **Two languages, one contract.** Python (`src/skills_mcp/registry_api.py`) and Go (`cli/internal/registry/registry.go`) speak the same endpoints in the same order with the same retry budget. Changes to either must update both — see [patterns and conventions](patterns-and-conventions.md).

## Picking up work

File an issue before writing code for anything non-trivial. The threshold is "would the diff need a design discussion?":

- **Trivial** (typos, dead-code removal, comment fixes, single-line bug fixes) — open a PR directly.
- **Non-trivial** (new MCP tool, new CLI subcommand, change to the registry contract, new dependency, change to the cache layout or config schema) — open an issue first. The maintainer's response usually clarifies scope and saves a rewrite.

Once the issue is acked or the change is trivial, branch off `main`, follow [development-workflow](development-workflow.md), and open a PR.

## PR checklist

Every PR should clear the following before review:

- [ ] **Tests pass locally.** `uv run pytest` and `(cd cli && go test ./...)` both green. CI runs the same suites; failing CI blocks merge.
- [ ] **Lint is clean.** `uv run ruff check .`, `uv run ruff format --check .`, and `(cd cli && gofmt -l .)` (must be empty), `go vet`, `staticcheck`, `deadcode -test`, and `gocyclo -over 15 -ignore "_test"` all pass.
- [ ] **README updated for user-visible changes.** If the PR changes a CLI flag, an MCP tool, an env var, the config schema, or the install flow, `README.md` needs to match. The website pitch is auto-mirrored from the README — don't edit it separately.
- [ ] **No new mandatory runtime dependency without a paragraph in the PR description explaining why.** Every dep is a future security and maintenance cost. Optional dev deps still need a one-liner.
- [ ] **Python and Go in sync.** Changes to the registry contract (`registry_api.py` ↔ `registry.go`) update both implementations and both test suites in the same PR. Path validators must agree.
- [ ] **PR description explains "why".** State the user-facing problem, then the approach. "What" is in the diff. "Why" is what reviewers need to know.
- [ ] **Conventional commit prefixes** (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `ci:`). The auto-release tagger reads them. See [development-workflow](development-workflow.md#commit-prefixes).
- [ ] **Cyclomatic-complexity ceilings respected.** Python 12 (ruff `C90`), Go 15 (`gocyclo`). New functions that exceed the limit get split into helpers; never raise the ceiling.

## What's in this section

- [Development workflow](development-workflow.md) — Clone, branch, test, PR, merge, release. The auto-release pipeline and how to force a minor or major bump.
- [Testing](testing.md) — The pytest suite (139 tests), the Go test layout, and the shared `gh` shim pattern both languages use to fake out GitHub.
- [Debugging](debugging.md) — Troubleshooting runbook. Symptoms → suspects, log-level toggles, where the config and cache live, how to run the MCP server inline, how to inspect the wizard model.
- [Tooling](tooling.md) — Every build/lint/test tool the repo uses, with pinned versions matching CI. Ruff config, staticcheck config, gofmt, pre-commit, and the release pipeline (hatch-vcs, goreleaser-style asset naming, codesign + notarize).
- [Patterns and conventions](patterns-and-conventions.md) — The two-language contract, naming rules, FastMCP server conventions, GitHub I/O safety rules, error-surface map.

## Cross-references

- [Getting started](../overview/getting-started.md) — install + first-run, both as a user and as a contributor.
- [Systems](../systems/index.md) — the cross-cutting machinery (registry client, cache, agent catalogue, JSON output, MCP-install cascade).
- [Apps](../apps/index.md) — per-deliverable deep dives (installer, CLI, MCP server, website).
- [Deployment](../deployment.md) — the release pipeline that ships every push to `main`.
