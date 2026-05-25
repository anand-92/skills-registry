"""Tests for the /github/webhook handler."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from key_value.aio.stores.memory import MemoryStore
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from skills_mcp.github_app import GitHubAppClient, GitHubAppCredentials, InstallationRepo
from skills_mcp.linking import DeliveryStore, LinkedRepo, LinkStore
from skills_mcp.webhooks import WebhookHandler


@pytest.fixture
def secret() -> str:
	return "very-secret-string"


@pytest.fixture
def kv() -> MemoryStore:
	return MemoryStore()


@pytest.fixture
def link_store(kv: MemoryStore) -> LinkStore:
	return LinkStore(kv)


@pytest.fixture
def delivery_store(kv: MemoryStore) -> DeliveryStore:
	return DeliveryStore(kv)


@pytest.fixture
def app_client_stub() -> GitHubAppClient:
	# A throwaway client; real network calls are replaced via AsyncMock in tests.
	return GitHubAppClient(
		GitHubAppCredentials(app_id="1", private_key_pem=_DUMMY_PEM),
	)


def test_handler_rejects_empty_secret(
	app_client_stub: GitHubAppClient,
	link_store: LinkStore,
	delivery_store: DeliveryStore,
) -> None:
	with pytest.raises(ValueError, match="secret"):
		WebhookHandler(
			secret="",
			app_client=app_client_stub,
			link_store=link_store,
			delivery_store=delivery_store,
		)


async def test_webhook_rejects_bad_signature(
	secret: str,
	app_client_stub: GitHubAppClient,
	link_store: LinkStore,
	delivery_store: DeliveryStore,
) -> None:
	handler = WebhookHandler(
		secret=secret,
		app_client=app_client_stub,
		link_store=link_store,
		delivery_store=delivery_store,
	)
	body = b'{"action":"created"}'
	request = _request(body, signature="sha256=wrong", event="installation")
	response = await handler(request)
	assert response.status_code == 401


async def test_webhook_accepts_ignored_event(
	secret: str,
	app_client_stub: GitHubAppClient,
	link_store: LinkStore,
	delivery_store: DeliveryStore,
) -> None:
	handler = WebhookHandler(
		secret=secret,
		app_client=app_client_stub,
		link_store=link_store,
		delivery_store=delivery_store,
	)
	body = b'{"action":"ping"}'
	request = _request(body, signature=_sig(secret, body), event="ping")
	response = await handler(request)
	assert response.status_code == 200
	assert b"ignored" in response.body


async def test_installation_created_links_repo_with_skills(
	secret: str,
	app_client_stub: GitHubAppClient,
	link_store: LinkStore,
	delivery_store: DeliveryStore,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	monkeypatch.setattr(
		app_client_stub,
		"mint_installation_token",
		AsyncMock(return_value="ghs_install_42"),
	)
	monkeypatch.setattr(
		app_client_stub,
		"list_installation_repos",
		AsyncMock(return_value=[InstallationRepo("alice/skills", "main")]),
	)
	# `repo_has_skills` makes a separate HTTP call; stub via httpx MockTransport.
	_install_mock_transport(
		monkeypatch,
		_handler(
			{
				"https://api.github.com/repos/alice/skills/contents/": [
					{"name": "foo", "type": "dir"}
				],
				"https://api.github.com/repos/alice/skills/contents/foo/SKILL.md": {
					"encoding": "base64",
					"content": "LS0tCm5hbWU6IEZvbwotLS0KaGV5Cg==",  # ---\nname: Foo\n---\nhey
				},
			}
		),
	)

	handler = WebhookHandler(
		secret=secret,
		app_client=app_client_stub,
		link_store=link_store,
		delivery_store=delivery_store,
	)
	body = json.dumps(
		{
			"action": "created",
			"installation": {"id": 42, "account": {"id": 1001}},
		}
	).encode("utf-8")
	request = _request(body, signature=_sig(secret, body), event="installation")

	response = await handler(request)
	assert response.status_code == 200
	link = await link_store.get_link("1001")
	assert link == LinkedRepo(installation_id=42, repo="alice/skills", default_branch="main")


async def test_installation_deleted_clears_link(
	secret: str,
	app_client_stub: GitHubAppClient,
	link_store: LinkStore,
	delivery_store: DeliveryStore,
) -> None:
	await link_store.set_link("u-9", LinkedRepo(99, "a/b", "main"))
	handler = WebhookHandler(
		secret=secret,
		app_client=app_client_stub,
		link_store=link_store,
		delivery_store=delivery_store,
	)
	body = json.dumps(
		{
			"action": "deleted",
			"installation": {"id": 99, "account": {"id": 9}},
		}
	).encode("utf-8")
	request = _request(body, signature=_sig(secret, body), event="installation")

	response = await handler(request)
	assert response.status_code == 200
	assert await link_store.get_link("u-9") is None
	assert await link_store.user_for_installation(99) is None


async def test_installation_created_picks_skills_named_repo_when_multiple(
	secret: str,
	app_client_stub: GitHubAppClient,
	link_store: LinkStore,
	delivery_store: DeliveryStore,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	monkeypatch.setattr(
		app_client_stub,
		"mint_installation_token",
		AsyncMock(return_value="ghs"),
	)
	monkeypatch.setattr(
		app_client_stub,
		"list_installation_repos",
		AsyncMock(
			return_value=[
				InstallationRepo("alice/notes", "main"),
				InstallationRepo("alice/skills", "main"),
				InstallationRepo("alice/blog", "main"),
			]
		),
	)
	# All three repos have valid SKILL.md content — selection should still
	# favour the one literally named `skills`.
	skill_blob = {
		"encoding": "base64",
		"content": "LS0tCm5hbWU6IFgKLS0tCg==",
	}
	_install_mock_transport(
		monkeypatch,
		_handler(
			{
				"https://api.github.com/repos/alice/notes/contents/": [
					{"name": "foo", "type": "dir"}
				],
				"https://api.github.com/repos/alice/notes/contents/foo/SKILL.md": skill_blob,
				"https://api.github.com/repos/alice/skills/contents/": [
					{"name": "bar", "type": "dir"}
				],
				"https://api.github.com/repos/alice/skills/contents/bar/SKILL.md": skill_blob,
				"https://api.github.com/repos/alice/blog/contents/": [
					{"name": "baz", "type": "dir"}
				],
				"https://api.github.com/repos/alice/blog/contents/baz/SKILL.md": skill_blob,
			}
		),
	)

	handler = WebhookHandler(
		secret=secret,
		app_client=app_client_stub,
		link_store=link_store,
		delivery_store=delivery_store,
	)
	body = json.dumps(
		{
			"action": "created",
			"installation": {"id": 11, "account": {"id": 222}},
		}
	).encode("utf-8")
	request = _request(body, signature=_sig(secret, body), event="installation")
	await handler(request)

	link = await link_store.get_link("222")
	assert link is not None
	assert link.repo == "alice/skills"


async def test_handler_works_when_mounted_as_starlette_route(
	secret: str,
	app_client_stub: GitHubAppClient,
	link_store: LinkStore,
	delivery_store: DeliveryStore,
) -> None:
	"""Regression test for the production-side mount path.

	The other tests call the handler instance directly with a fabricated
	``Request``, which bypasses Starlette's routing. Starlette treats
	class instances with ``__call__`` as ASGI3 apps and dispatches them
	with ``(scope, receive, send)`` — passing such an instance to
	``Route(endpoint=...)`` raises ``TypeError: __call__() takes 2
	positional arguments but 4 were given`` on every request.

	``remote_server._register_routes`` wraps the handler in a plain
	``async def`` to force the endpoint dispatch path. This test
	reproduces that mount path and asserts a real POST through the ASGI
	stack returns 401 (bad signature) rather than 500.
	"""
	handler = WebhookHandler(
		secret=secret,
		app_client=app_client_stub,
		link_store=link_store,
		delivery_store=delivery_store,
	)

	async def endpoint(request: Request) -> Response:
		return await handler(request)

	app = Starlette(routes=[Route("/github/webhook", endpoint, methods=["POST"])])
	transport = httpx.ASGITransport(app=app)
	async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
		resp = await client.post(
			"/github/webhook",
			content=b'{"action":"created"}',
			headers={
				"X-Hub-Signature-256": "sha256=wrong",
				"X-GitHub-Event": "installation",
				"Content-Type": "application/json",
			},
		)
	assert resp.status_code == 401


async def test_replayed_delivery_is_deduped(
	secret: str,
	app_client_stub: GitHubAppClient,
	link_store: LinkStore,
	delivery_store: DeliveryStore,
) -> None:
	"""Re-delivering the same X-GitHub-Delivery short-circuits.

	The second call must return 200 with a ``deduped`` body and must NOT
	re-run the handler logic — we verify that by pre-populating the link
	store and confirming it's untouched by a replay of an
	``installation.deleted`` payload that would otherwise wipe it.
	"""
	await link_store.set_link("u-77", LinkedRepo(77, "a/b", "main"))
	handler = WebhookHandler(
		secret=secret,
		app_client=app_client_stub,
		link_store=link_store,
		delivery_store=delivery_store,
	)
	body = json.dumps(
		{
			"action": "deleted",
			"installation": {"id": 77, "account": {"id": 77}},
		}
	).encode("utf-8")

	# First delivery: handler runs, link is dropped, delivery is marked.
	first = await handler(
		_request(body, signature=_sig(secret, body), event="installation", delivery_id="d-1")
	)
	assert first.status_code == 200
	assert await link_store.get_link("u-77") is None

	# Re-link the user so we can prove the replay doesn't re-mutate state.
	await link_store.set_link("u-77", LinkedRepo(77, "a/b", "main"))

	# Replay the exact same delivery — should be a no-op dedupe response.
	replay = await handler(
		_request(body, signature=_sig(secret, body), event="installation", delivery_id="d-1")
	)
	assert replay.status_code == 200
	assert b"deduped" in replay.body
	# Link still present — replay did not run the deleted handler again.
	assert await link_store.get_link("u-77") is not None


async def test_delivery_marks_after_ignored_event(
	secret: str,
	app_client_stub: GitHubAppClient,
	link_store: LinkStore,
	delivery_store: DeliveryStore,
) -> None:
	"""Ignored events still consume the delivery ID so replays no-op."""
	handler = WebhookHandler(
		secret=secret,
		app_client=app_client_stub,
		link_store=link_store,
		delivery_store=delivery_store,
	)
	body = b'{"action":"ping"}'
	first = await handler(
		_request(body, signature=_sig(secret, body), event="ping", delivery_id="d-9")
	)
	assert first.status_code == 200
	assert b"ignored" in first.body

	replay = await handler(
		_request(body, signature=_sig(secret, body), event="ping", delivery_id="d-9")
	)
	assert b"deduped" in replay.body


async def test_missing_delivery_header_does_not_dedupe(
	secret: str,
	app_client_stub: GitHubAppClient,
	link_store: LinkStore,
	delivery_store: DeliveryStore,
) -> None:
	"""Two payloads without a delivery ID both run (no dedupe key)."""
	handler = WebhookHandler(
		secret=secret,
		app_client=app_client_stub,
		link_store=link_store,
		delivery_store=delivery_store,
	)
	body = b'{"action":"ping"}'
	# Both should hit the ignored-event branch with no dedupe in between.
	first = await handler(_request(body, signature=_sig(secret, body), event="ping"))
	second = await handler(_request(body, signature=_sig(secret, body), event="ping"))
	assert b"ignored" in first.body
	assert b"ignored" in second.body


# ------------------------------------------------------------ helpers


_DUMMY_PEM = "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----\n"


def _sig(secret: str, body: bytes) -> str:
	return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _request(body: bytes, *, signature: str, event: str, delivery_id: str = "") -> Request:
	"""Build a minimal Starlette Request that .body() will return ``body`` for.

	``delivery_id`` becomes the ``X-GitHub-Delivery`` header (empty string
	omits the header, which is what older tests pre-dating dedupe expect).
	"""

	async def receive() -> dict[str, Any]:
		return {"type": "http.request", "body": body, "more_body": False}

	headers: list[tuple[bytes, bytes]] = [
		(b"x-hub-signature-256", signature.encode("ascii")),
		(b"x-github-event", event.encode("ascii")),
		(b"content-type", b"application/json"),
	]
	if delivery_id:
		headers.append((b"x-github-delivery", delivery_id.encode("ascii")))

	scope = {
		"type": "http",
		"method": "POST",
		"path": "/github/webhook",
		"raw_path": b"/github/webhook",
		"query_string": b"",
		"root_path": "",
		"headers": headers,
	}
	return Request(scope, receive)  # type: ignore[arg-type]


def _install_mock_transport(
	monkeypatch: pytest.MonkeyPatch,
	handler: Callable[[httpx.Request], httpx.Response],
) -> None:
	real = httpx.AsyncClient

	def fake(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
		kwargs["transport"] = httpx.MockTransport(handler)
		return real(*args, **kwargs)

	monkeypatch.setattr(httpx, "AsyncClient", fake)


def _handler(responses: dict[str, Any]) -> Callable[[httpx.Request], httpx.Response]:
	def _inner(request: httpx.Request) -> httpx.Response:
		key = str(request.url).split("?", 1)[0]
		body = responses.get(key)
		if body is None:
			return httpx.Response(404, text=f"unmocked: {key}")
		return httpx.Response(200, json=body)

	return _inner
