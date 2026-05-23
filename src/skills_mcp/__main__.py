"""Entry point: ``python -m skills_mcp`` and the ``skills-registry`` console script.

Owns the ``skills-registry init`` subcommand that bootstraps a GitHub-backed
registry by delegating to the ``skill-registry`` Go CLI. The MCP server
itself lives in :mod:`skills_mcp.registry_server` and is exposed via the
``skill-registry-mcp`` console script.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from . import __version__


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(
		prog="skills-registry",
		description=(
			"GitHub-backed skill registry. Run `skills-registry init` to create "
			"a registry repo and install the `skill-registry` CLI. The MCP "
			"server itself is `skill-registry-mcp` (installed alongside)."
		),
	)
	parser.add_argument(
		"--version",
		action="version",
		version=f"skills-registry {__version__}",
	)

	subparsers = parser.add_subparsers(dest="command", metavar="<command>")

	# `init` — bootstrap a GitHub-backed registry. Defined in its own module
	# so the import is deferred to when it's actually used.
	from .init import register_subparser as _register_init

	_register_init(subparsers)

	args = parser.parse_args(argv)

	logging.basicConfig(
		level=os.environ.get("SKILLS_LOG_LEVEL", "INFO").upper(),
		format="%(asctime)s %(levelname)s %(name)s: %(message)s",
		stream=sys.stderr,
	)

	if args.command == "init":
		from .init import cmd_init

		return cmd_init(args)

	# No subcommand given — print help and exit non-zero so scripts notice.
	parser.print_help(sys.stderr)
	return 1


if __name__ == "__main__":
	sys.exit(main())
