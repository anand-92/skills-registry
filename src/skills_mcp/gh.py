"""GitHub CLI lookup and small helpers.

Desktop MCP clients (Claude Desktop, Cursor, VS Code) launch the MCP server
without inheriting a user shell's ``PATH``. ``shutil.which("gh")`` returns
``None`` even when ``gh`` is installed and the user can run it from a
terminal. :func:`find_gh` walks a curated list of fallback locations so the
server can keep working in those environments.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

# Fallback search paths, ordered by likelihood on macOS/Linux.
_FALLBACK_GH_PATHS: tuple[Path, ...] = (
	Path.home() / ".local" / "bin" / "gh",
	Path("/opt/homebrew/bin/gh"),
	Path("/usr/local/bin/gh"),
	Path("/usr/bin/gh"),
	Path.home() / "bin" / "gh",
)


class GhNotFoundError(RuntimeError):
	"""Raised when no usable ``gh`` binary can be located."""


class GhNotAuthedError(RuntimeError):
	"""Raised when ``gh`` is installed but not authenticated."""


def find_gh() -> Path:
	"""Locate a usable ``gh`` binary.

	Looks at ``PATH`` first, then a curated list of common install locations.
	Raises :class:`GhNotFoundError` with a copy-pasteable hint if nothing works.
	"""
	from_path = shutil.which("gh")
	if from_path:
		return Path(from_path)
	for candidate in _FALLBACK_GH_PATHS:
		if candidate.is_file() and os.access(candidate, os.X_OK):
			return candidate
	raise GhNotFoundError(
		"GitHub CLI (`gh`) not found on PATH or in common install locations.\n"
		"Install it from https://cli.github.com/ and run `gh auth login`."
	)


def ensure_authed(gh: Path | None = None) -> Path:
	"""Verify ``gh`` is installed *and* authenticated. Returns the binary path."""
	gh = gh or find_gh()
	result = subprocess.run(
		[str(gh), "auth", "status"],
		capture_output=True,
		text=True,
		check=False,
	)
	if result.returncode != 0:
		raise GhNotAuthedError(
			"GitHub CLI is installed but not authenticated. Run `gh auth login` and try again."
		)
	return gh


def gh_api(
	endpoint: str,
	*,
	method: str = "GET",
	fields: dict[str, str] | None = None,
	input_json: dict | None = None,
	gh: Path | None = None,
) -> dict | list:
	"""Call ``gh api <endpoint>`` and return parsed JSON.

	``input_json`` POSTs the dict as the request body (no shell escaping
	headaches). ``fields`` becomes ``-f key=value`` arguments for simple
	query-string parameters on GET.
	"""
	gh = gh or find_gh()
	cmd = [str(gh), "api", "-X", method, endpoint, "-H", "Accept: application/vnd.github+json"]
	for key, val in (fields or {}).items():
		cmd.extend(["-f", f"{key}={val}"])
	stdin_data: str | None = None
	if input_json is not None:
		cmd.append("--input")
		cmd.append("-")
		stdin_data = json.dumps(input_json)
	result = subprocess.run(
		cmd,
		input=stdin_data,
		capture_output=True,
		text=True,
		check=False,
	)
	if result.returncode != 0:
		raise GhApiError.from_subprocess(endpoint, method, result)
	if not result.stdout.strip():
		return {}
	return json.loads(result.stdout)


class GhApiError(RuntimeError):
	"""Raised when ``gh api`` returns a non-zero exit code."""

	def __init__(self, endpoint: str, method: str, status: int, body: str) -> None:
		super().__init__(f"gh api {method} {endpoint} failed (status {status}): {body}")
		self.endpoint = endpoint
		self.method = method
		self.status = status
		self.body = body

	@classmethod
	def from_subprocess(
		cls, endpoint: str, method: str, result: subprocess.CompletedProcess
	) -> GhApiError:
		import re

		body = (result.stderr or result.stdout or "").strip()
		# Find the first 3-digit HTTP status code mentioned in the error body.
		match = re.search(r"\b([1-5][0-9]{2})\b", body)
		status = int(match.group(1)) if match else 0
		return cls(endpoint=endpoint, method=method, status=status, body=body)
