# Primitives

The "primitives" pages document the small set of domain types that show up everywhere else: in the API surfaces, in the systems modules, in the CLI subcommands, in the MCP tools, in the wizard, in the hub. Two types do all the work.

## The two types

| Type | Lives in | Used by |
| --- | --- | --- |
| [Skill](skill.md) | `scan.Skill` (Go), `SkillSummary` (Python) | `list_skills`, `get_skill`, `publish_skill`, every CLI subcommand, the hub, the wizard. |
| [Registry config](registry-config.md) | `RegistryConfig` (Python), `config.Config` (Go) | Every entrypoint: `build_server()`, `runRoot`, every subcommand's first call. |

`Skill` is the unit of distribution: a folder with a `SKILL.md` at its root, an optional manifest in YAML-ish frontmatter, and any supporting files the skill author chose to ship. `RegistryConfig` is the resolved identity of the GitHub repo the user is connected to — the env var or TOML file that tells both the Python server and the Go CLI which `owner/repo` to talk to.

Both types are deliberately tiny. The full Skill record is five fields; the full Config record is two. Nothing else qualifies as "primitive" in this codebase because every other shape (the registry client, the cache, the wizard model, the hub model) is either a transient or a higher-level object built from these two.

## Why these two

A "skill" is what the registry stores; a "config" is what tells the code which registry. Once you have both, every operation in the system is a composition of:

```
config.Load() → registry.Client(repo) → operation(slug, …)
```

Read [skill.md](skill.md) for the slugify algorithm and frontmatter contract; read [registry-config.md](registry-config.md) for the resolution order and TOML format. Both implementations exist in parallel Python and Go versions, and they are deliberately kept in lockstep so the MCP server (which a desktop client launches) and the CLI (which the user types) agree on every byte of every identifier.

## Cross-cutting references

- [../systems/registry-client.md](../systems/registry-client.md) — the API client that consumes both primitives.
- [../reference/configuration.md](../reference/configuration.md) — the configuration knobs (env vars, XDG paths, TOML keys).
- [../api/mcp-tools.md](../api/mcp-tools.md) and [../api/cli-commands.md](../api/cli-commands.md) — the surfaces that operate on these types.
