"""Integration-style tests for the rate-limit middleware behavior.

These exercise the *real* :class:`RateLimitingMiddleware` from FastMCP
plugged into our :func:`client_id_from_token` keying. We don't mock the
limiter itself — that would test our test code, not the production stack.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastmcp.server.middleware.middleware import MiddlewareContext
from fastmcp.server.middleware.rate_limiting import RateLimitError, RateLimitingMiddleware

from skills_mcp.middleware import BURST_CAPACITY, client_id_from_token


@pytest.fixture
def rate_limiter() -> RateLimitingMiddleware:
	# Match the production wiring so the test exercises identical state.
	return RateLimitingMiddleware(
		max_requests_per_second=5.0,
		burst_capacity=BURST_CAPACITY,
		get_client_id=client_id_from_token,
		global_limit=False,
	)


async def test_burst_within_budget_passes(
	rate_limiter: RateLimitingMiddleware, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Up to burst_capacity calls in a tight loop all succeed."""
	_stub_token(monkeypatch, sub="user-A")
	call_count = 0

	async def call_next(_ctx: Any) -> str:
		nonlocal call_count
		call_count += 1
		return "ok"

	for _ in range(BURST_CAPACITY):
		result = await rate_limiter.on_request(_ctx("tools/call"), call_next)
		assert result == "ok"
	assert call_count == BURST_CAPACITY


async def test_burst_exceeded_raises_rate_limit_error(
	rate_limiter: RateLimitingMiddleware, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""The (burst_capacity + 1)th immediate call is rejected.

	Token-bucket math: refill rate is 5/s, so a single extra call after
	exhausting the burst won't have had time to replenish a token.
	"""
	_stub_token(monkeypatch, sub="user-B")

	async def call_next(_ctx: Any) -> str:
		return "ok"

	for _ in range(BURST_CAPACITY):
		await rate_limiter.on_request(_ctx("tools/call"), call_next)
	with pytest.raises(RateLimitError):
		await rate_limiter.on_request(_ctx("tools/call"), call_next)


async def test_per_user_buckets_are_independent(
	rate_limiter: RateLimitingMiddleware, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""User A burning their bucket has no effect on user B's calls."""

	async def call_next(_ctx: Any) -> str:
		return "ok"

	# Burn A's burst.
	_stub_token(monkeypatch, sub="user-A")
	for _ in range(BURST_CAPACITY):
		await rate_limiter.on_request(_ctx("tools/call"), call_next)
	with pytest.raises(RateLimitError):
		await rate_limiter.on_request(_ctx("tools/call"), call_next)

	# Switch to B mid-test — B has a fresh bucket.
	_stub_token(monkeypatch, sub="user-B")
	result = await rate_limiter.on_request(_ctx("tools/call"), call_next)
	assert result == "ok"


async def test_unauthenticated_path_shares_anonymous_bucket(
	rate_limiter: RateLimitingMiddleware, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""All token-less requests share a single bucket keyed on ``anonymous``.

	Auth provider rejects unauthenticated requests before middleware runs
	in production, so this bucket should normally have zero traffic. The
	test confirms the fallback key works deterministically — without it,
	a bug that lost the token would hand each missing-token request its
	own private bucket and let attackers cycle past the limit.
	"""
	monkeypatch.setattr("skills_mcp.middleware.get_access_token", lambda: None)

	async def call_next(_ctx: Any) -> str:
		return "ok"

	for _ in range(BURST_CAPACITY):
		await rate_limiter.on_request(_ctx("tools/call"), call_next)
	with pytest.raises(RateLimitError):
		await rate_limiter.on_request(_ctx("tools/call"), call_next)


# ------------------------------------------------------------ helpers


def _stub_token(monkeypatch: pytest.MonkeyPatch, *, sub: str) -> None:
	token = SimpleNamespace(claims={"sub": sub})
	monkeypatch.setattr("skills_mcp.middleware.get_access_token", lambda: token)


def _ctx(method: str) -> MiddlewareContext:
	# RateLimitingMiddleware.on_request only reads ``context.method`` to
	# decide whether to limit (it skips notifications). Anything object-y
	# with that attribute is enough — building a real MiddlewareContext
	# requires a live MCP session we don't need here.
	return SimpleNamespace(  # type: ignore[return-value]
		method=method,
		source="mcp",
		type="request",
	)
