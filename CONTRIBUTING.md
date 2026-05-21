# Contributing to skills-mcp

Thanks for your interest! `skills-mcp` is intentionally small: a folder of `SKILL.md` files exposed over MCP. We want to keep it that way. Bug fixes, docs, and small focused features are very welcome. For anything larger, **please open an issue first** so we can agree on scope before you write code.

## Ethos

- **Small and focused.** One feature, one PR. If a change adds new mandatory dependencies, a new env var, or new public surface, it needs an issue first.
- **No magic.** A user should be able to read the code in one sitting.
- **Backwards-compatible by default.** Breaking changes to env vars, resource URIs, or CLI flags need a deprecation note.

## Development setup

You need Python 3.10+ and [uv](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/anand-92/skills-mcp
cd skills-mcp
uv sync --group dev
```

That installs the package in editable mode along with the dev dependencies.

## Running tests

```bash
uv run pytest
```

Add or update tests for any behavior change. If you fix a bug, add a regression test that fails before your fix.

## Lint and format

We use [ruff](https://github.com/astral-sh/ruff) for both linting and formatting.

```bash
uv run ruff check .
uv run ruff format .
```

CI runs `ruff check` and `pytest`. Both must pass.

## Pre-commit

Install the git hooks so you catch issues before pushing:

```bash
uv run pre-commit install
```

## Commit messages

Use conventional-commit-ish prefixes — they make the changelog readable:

- `fix:` bug fix
- `feat:` new user-visible feature
- `docs:` README, examples, contributing
- `refactor:` no behavior change
- `test:` tests only
- `chore:` build, deps, tooling

Example: `fix: ignore SKILL.md files under hidden directories`.

## Pull request checklist

Before opening the PR, please confirm:

- [ ] Tests pass locally (`uv run pytest`).
- [ ] `uv run ruff check .` is clean.
- [ ] `README.md` is updated if you changed anything user-visible (env vars, CLI, behavior).
- [ ] No new **mandatory** runtime dependencies. Optional ones need justification in the PR description.
- [ ] The PR description explains *why*, not just *what*.

## Reporting bugs

Use the **Bug report** issue template. Please include:

- `skills-mcp --version`
- Your MCP client and its version
- OS and Python version
- The value of `SKILLS_ROOT`
- A minimal reproduction (a tiny `SKILL.md` is usually enough)

## Security issues

Please do **not** open a public issue. See [SECURITY.md](SECURITY.md).
