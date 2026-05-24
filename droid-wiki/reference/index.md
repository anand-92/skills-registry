# Reference

Look-up material for `skills-registry`. Use this section when you already know what you want and just need the exact knob, flag, or list.

## Pages

- [Configuration](configuration.md) — environment variables, config file format, XDG paths, resolution order.
- [Agents catalogue](agents-catalogue.md) — the 56-entry dot-folder table consumed by the wizard's multi-select and the `add`/`sync` flows.
- [Dependencies](dependencies.md) — Python runtime, Go runtime, dev tooling, website stack, and the rationale for keeping the runtime surface tiny.

## What lives elsewhere

- API contracts for the three MCP tools and the seven Go subcommands are in [../api/](../api/index.md).
- Per-component deep dives are in [../systems/](../systems/index.md).
- Security model is on its own page at [../security.md](../security.md).
- Release / deployment pipeline is at [../deployment.md](../deployment.md).
- Architectural rationale (why two upload paths, why a Go CLI when the server is Python) is in [../background/design-decisions.md](../background/design-decisions.md).
