# Background

Why `skills-registry` is shaped the way it is. The reference and systems pages cover **what** the code does; this section covers **why** it does it that way.

## Pages

- [Design decisions](design-decisions.md) — the rationale behind the non-obvious choices: two upload paths (gh-api for the MCP server, git push for bootstrap), a Go CLI fronting a Python server, the hand-rolled frontmatter parser, the `gh`-only credential anchor, the pure routing function for bare-command UX, the uv → pipx → pip install cascade, plus the current known limitations and future-work backlog.

## Why this section exists

When you read `cli/internal/registry/registry.go:PushTreeViaGit` for the first time it is reasonable to ask, "why do we shell out to git here when the rest of the codebase carefully avoids it?" Answers like that are hard to recover from the code alone — they sit at the intersection of GitHub's rate-limit behavior, the constraints of the desktop-MCP subprocess environment, and historical context from earlier project iterations.

The [Design decisions](design-decisions.md) page is the durable place to write those answers down so future contributors (human or agent) do not have to reconstruct them from PR archaeology.

See also:

- [../overview/](../overview/index.md) for the high-level pitch and the user journey.
- [../systems/](../systems/index.md) for component-by-component deep dives.
- [../reference/](../reference/index.md) for the look-up material.
