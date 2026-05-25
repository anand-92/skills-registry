"""Tests for the production middleware stack wiring."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware
from fastmcp.server.middleware.logging import StructuredLoggingMiddleware
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware

from skills_mcp.middleware import (
	BURST_CAPACITY,
	MAX_REQUESTS_PER_SECOND,
	build_middleware_stack,
	client_id_from_token,
)


def test_middleware_stack_order() -> None:
	"""ErrorHandling → RateLimiting → StructuredLogging.

	Order matters: error handling outermost catches everything; rate
	limiting next so blocked requests never reach the logger; structured
	logging innermost so it records what actually executed.
	"""
	stack = build_middleware_stack()
	assert len(stack) == 3
	assert isinstance(stack[0], ErrorHandlingMiddleware)
	assert isinstance(stack[1], RateLimitingMiddleware)
	assert isinstance(stack[2], StructuredLoggingMiddleware)


def test_rate_limiter_configured_from_module_constants() -> None:
	stack = build_middleware_stack()
	rl = stack[1]
	assert isinstance(rl, RateLimitingMiddleware)
	# RateLimitingMiddleware stores its config on a TokenBucketRateLimiter
	# factory; the public surface is the constructor args reflected on
	# the instance attributes.
	assert rl.max_requests_per_second == MAX_REQUESTS_PER_SECOND
	assert rl.burst_capacity == BURST_CAPACITY
	# Per-client mode, not global.
	assert rl.global_limit is False
	# get_client_id was bound (it's our function, not the default).
	assert rl.get_client_id is client_id_from_token


def test_client_id_from_token_returns_anonymous_without_token(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	monkeypatch.setattr("skills_mcp.middleware.get_access_token", lambda: None)
	assert client_id_from_token(_dummy_ctx()) == "anonymous"


def test_client_id_from_token_returns_sub_when_present(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	token = SimpleNamespace(claims={"sub": "12345", "login": "alice"})
	monkeypatch.setattr("skills_mcp.middleware.get_access_token", lambda: token)
	assert client_id_from_token(_dummy_ctx()) == "12345"


def test_client_id_falls_back_to_anonymous_when_sub_missing(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	token = SimpleNamespace(claims={"login": "anon-but-no-sub"})
	monkeypatch.setattr("skills_mcp.middleware.get_access_token", lambda: token)
	# Defensive — the OAuth path always issues tokens with ``sub``, but
	# we never want a malformed token to inherit another user's bucket.
	assert client_id_from_token(_dummy_ctx()) == "anonymous"


def test_client_id_coerces_non_string_sub(monkeypatch: pytest.MonkeyPatch) -> None:
	# GitHub's ``sub`` is a numeric user ID. PyJWT may decode it as int
	# depending on provider config; we coerce so the dict key is stable.
	token = SimpleNamespace(claims={"sub": 999})
	monkeypatch.setattr("skills_mcp.middleware.get_access_token", lambda: token)
	assert client_id_from_token(_dummy_ctx()) == "999"


def _dummy_ctx() -> Any:
	"""MiddlewareContext stub — the client_id_func only reads via get_access_token."""
	return SimpleNamespace(method="tools/list", source="mcp", type="request")
