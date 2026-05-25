"""Tests for the PostHog analytics client builder.

The module-level ``posthog_client`` is built once at import time, so these
tests exercise ``_build_client`` directly rather than reloading the
module (reloads break the singleton contract relied on by every other
``posthog_client.capture(...)`` call site).
"""

from __future__ import annotations

import importlib
import sys
from typing import Any

import pytest

from skills_mcp import analytics


def test_noop_capture_is_silent() -> None:
	"""``_NoopPosthog.capture`` accepts any args and returns ``None``.

	Every capture-site in the codebase passes ``distinct_id=...``,
	``event=...``, and (sometimes) ``properties={...}``. The noop must
	swallow all of them without raising — that's the contract that lets
	the server run without ``POSTHOG_PROJECT_TOKEN`` set.
	"""
	noop = analytics._NoopPosthog()
	# Positional, keyword, mixed — all must no-op.
	assert noop.capture("evt") is None
	assert noop.capture(distinct_id="u-1", event="evt") is None
	assert noop.capture("u-1", event="evt", properties={"k": "v"}) is None
	assert noop.shutdown() is None


def test_build_client_returns_noop_when_token_unset(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Missing ``POSTHOG_PROJECT_TOKEN`` → ``_NoopPosthog``.

	This is the path CI, local dev, and any deploy that forgot the env
	var hit. We assert the class identity, not just behaviour, so a
	silent regression to "create a real client with token=''" would
	fail loudly.
	"""
	monkeypatch.delenv("POSTHOG_PROJECT_TOKEN", raising=False)
	client = analytics._build_client()
	assert isinstance(client, analytics._NoopPosthog)


def test_build_client_treats_whitespace_token_as_unset(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Leading/trailing whitespace doesn't count as configured."""
	monkeypatch.setenv("POSTHOG_PROJECT_TOKEN", "   ")
	client = analytics._build_client()
	assert isinstance(client, analytics._NoopPosthog)


def test_build_client_constructs_real_posthog_when_token_set(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Token present → real ``Posthog`` instance with the configured args.

	We patch the import path the builder uses so we don't open a real
	network connection during tests. The fake records constructor args
	so we can assert ``enable_exception_autocapture=True`` and the host
	override are passed through.
	"""
	captured: dict[str, Any] = {}

	class FakePosthog:
		def __init__(self, token: str, **kwargs: Any) -> None:
			captured["token"] = token
			captured["kwargs"] = kwargs

	fake_module = type(sys)("posthog")
	fake_module.Posthog = FakePosthog  # type: ignore[attr-defined]
	monkeypatch.setitem(sys.modules, "posthog", fake_module)
	monkeypatch.setenv("POSTHOG_PROJECT_TOKEN", "phc_abc123")
	monkeypatch.setenv("POSTHOG_HOST", "https://eu.i.posthog.com")

	client = analytics._build_client()
	assert isinstance(client, FakePosthog)
	assert captured["token"] == "phc_abc123"
	# Exception autocapture is part of the documented analytics contract
	# (see docs/registry.md §4.1) — pin it here so a refactor can't
	# silently drop it.
	assert captured["kwargs"]["enable_exception_autocapture"] is True
	assert captured["kwargs"]["host"] == "https://eu.i.posthog.com"


def test_build_client_omits_host_when_env_blank(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Unset ``POSTHOG_HOST`` must NOT show up in the SDK kwargs.

	Passing ``host=""`` to the real SDK overrides the documented default
	(US cloud) with an invalid URL. Asserting the key is missing —
	rather than asserting it's empty — guards against that footgun.
	"""
	captured: dict[str, Any] = {}

	class FakePosthog:
		def __init__(self, token: str, **kwargs: Any) -> None:
			captured["kwargs"] = kwargs

	fake_module = type(sys)("posthog")
	fake_module.Posthog = FakePosthog  # type: ignore[attr-defined]
	monkeypatch.setitem(sys.modules, "posthog", fake_module)
	monkeypatch.setenv("POSTHOG_PROJECT_TOKEN", "phc_abc")
	monkeypatch.delenv("POSTHOG_HOST", raising=False)

	analytics._build_client()
	assert "host" not in captured["kwargs"]


def test_build_client_falls_back_to_noop_on_constructor_failure(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""SDK init blowing up must NOT take down the server.

	A bad token, a network blip during the SDK's own startup, or a
	future SDK that raises on import-time validation — none of these
	should crash the hosted MCP boot path. ``_build_client`` swallows
	the exception and returns the noop stub.
	"""

	class ExplodingPosthog:
		def __init__(self, *_args: Any, **_kwargs: Any) -> None:
			raise RuntimeError("simulated SDK init failure")

	fake_module = type(sys)("posthog")
	fake_module.Posthog = ExplodingPosthog  # type: ignore[attr-defined]
	monkeypatch.setitem(sys.modules, "posthog", fake_module)
	monkeypatch.setenv("POSTHOG_PROJECT_TOKEN", "phc_abc")

	client = analytics._build_client()
	assert isinstance(client, analytics._NoopPosthog)


def test_module_singleton_is_noop_in_test_env() -> None:
	"""The shared ``posthog_client`` is the noop in CI / local pytest.

	pytest runs without ``POSTHOG_PROJECT_TOKEN`` set, so the module-
	level singleton must be the stub. Every other test that asserts
	captures by monkey-patching ``posthog_client.capture`` depends on
	this — if it were ever a real client by accident, tests would emit
	to PostHog from CI.
	"""
	# This test is order-independent: it inspects the module the rest
	# of the suite has been importing the whole time.
	assert isinstance(analytics.posthog_client, analytics._NoopPosthog)
	# Sanity: re-importing the module by name returns the same object.
	again = importlib.import_module("skills_mcp.analytics")
	assert again.posthog_client is analytics.posthog_client
