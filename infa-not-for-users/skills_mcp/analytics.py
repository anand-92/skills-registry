"""Shared PostHog analytics client for the hosted MCP server.

Initialized once from environment variables and shared across all request
handlers. The PostHog SDK queues events in a background thread so capture()
calls are non-blocking and safe to call from async handlers.

If POSTHOG_PROJECT_TOKEN is not set the module creates a no-op stub so
analytics failures never affect the server's core functionality.
"""

from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger("skills_mcp.analytics")

_POSTHOG_TOKEN_ENV = "POSTHOG_PROJECT_TOKEN"
_POSTHOG_HOST_ENV = "POSTHOG_HOST"


class _NoopPosthog:
	"""Drop-in stub when PostHog is not configured."""

	def capture(self, *_args: Any, **_kwargs: Any) -> None:
		pass

	def shutdown(self) -> None:
		pass


def _build_client() -> Any:
	token = os.environ.get(_POSTHOG_TOKEN_ENV, "").strip()
	if not token:
		log.info("PostHog not configured (%s not set); analytics disabled", _POSTHOG_TOKEN_ENV)
		return _NoopPosthog()
	try:
		from posthog import Posthog

		host = os.environ.get(_POSTHOG_HOST_ENV, "").strip()
		kwargs: dict[str, Any] = {"enable_exception_autocapture": True}
		if host:
			kwargs["host"] = host
		client = Posthog(token, **kwargs)
		log.info("PostHog analytics enabled")
		return client
	except Exception:
		log.exception("Failed to initialize PostHog; analytics disabled")
		return _NoopPosthog()


posthog_client = _build_client()

__all__ = ["posthog_client"]
