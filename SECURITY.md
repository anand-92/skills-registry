# Security policy

## Reporting a vulnerability

If you believe you have found a security issue in `skills-mcp`, please report it **privately** via [GitHub Security Advisories](https://github.com/anand-92/skills-mcp/security/advisories/new).

Do **not** open a public GitHub issue, discussion, or pull request for security problems. Public reports give attackers a head start before a fix lands.

When you report, please include:

- A description of the issue and its impact.
- Steps to reproduce, ideally with a minimal `SKILL.md` or directory layout.
- The version of `skills-mcp` (`skills-mcp --version`), your Python version, and OS.
- Any logs or stack traces you can share.

We will acknowledge your report, investigate, and coordinate a fix and disclosure timeline with you. Credit in the release notes is offered by default; let us know if you'd prefer to stay anonymous.

## Scope and threat model

`skills-mcp` is a local MCP server. It reads any file under the directories listed in `SKILLS_ROOT` and exposes them as MCP resources and tools. Anything reachable from those roots is visible to the connected MCP client and, transitively, to the model.

**Do not** place any of the following inside a `SKILLS_ROOT`:

- Secrets, API keys, tokens, or passwords.
- `.env` files or other credential stores.
- PII or anything covered by data-handling regulations you care about.
- Private source code you do not want sent to a model.

Treat a skills directory like a public README directory: assume the model can read everything in it.

Vulnerabilities we care about include (non-exhaustive):

- Path traversal that lets a skill read files outside its declared root.
- Resource URIs that disclose unintended paths.
- Crashes or hangs triggered by maliciously crafted `SKILL.md` files.
- Supply-chain issues in our published distributions.

Out of scope:

- Risks inherent to the model or MCP client consuming a skill (jailbreaks, prompt injection in skill content, etc.). Skills are user-controlled prompts; treat them with the same care as any other prompt.
- Issues that require the attacker to already have write access to your `SKILLS_ROOT`.

## Supported versions

We support the **latest minor release on `main`**. Older versions do not receive security backports — please upgrade if you can.
