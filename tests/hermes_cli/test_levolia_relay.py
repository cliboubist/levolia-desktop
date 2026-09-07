"""Tests for the Levolia model relay (``/api/llm/*``)."""
from __future__ import annotations

import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hermes_cli import levolia_relay
from hermes_cli.dashboard_auth.public_paths import is_public_api_path

TOKEN = "relay-secret-token"


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("LEVOLIA_RELAY_TOKEN", TOKEN)
    monkeypatch.setattr(
        levolia_relay,
        "_resolve_upstream",
        lambda: {
            "provider": "openrouter",
            "api_mode": "chat_completions",
            "base_url": "https://upstream.example/v1",
            "api_key": "sk-server-secret",
        },
    )
    monkeypatch.setattr(levolia_relay, "_server_model_config", lambda: {"default": "server/model-x", "provider": "openrouter"})
    application = FastAPI()
    application.include_router(levolia_relay.router)
    return application


def _install_fake_upstream(monkeypatch, handler):
    def make_client():
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(levolia_relay, "_make_client", make_client)


def test_relay_prefix_is_exempt_from_dashboard_gates():
    assert is_public_api_path("/api/llm/chat/completions")
    assert is_public_api_path("/api/llm/info")
    assert not is_public_api_path("/api/llmx")
    assert not is_public_api_path("/api/sessions")


def test_missing_or_wrong_token_is_rejected(app):
    client = TestClient(app)
    assert client.get("/api/llm/info").status_code == 401
    assert client.get("/api/llm/info", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_relay_disabled_without_token(app, monkeypatch):
    monkeypatch.delenv("LEVOLIA_RELAY_TOKEN", raising=False)
    monkeypatch.delenv("HERMES_DASHBOARD_SESSION_TOKEN", raising=False)
    monkeypatch.setattr(levolia_relay, "relay_token", lambda: "")
    client = TestClient(app)
    assert client.get("/api/llm/info", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 503


def test_info_mirrors_server_model_without_secrets(app):
    client = TestClient(app)
    res = client.get("/api/llm/info", headers={"Authorization": f"Bearer {TOKEN}"})
    assert res.status_code == 200
    body = res.json()
    assert body == {
        "provider": "openrouter",
        "model": "server/model-x",
        "api_mode": "chat_completions",
        "upstream_host": "upstream.example",
    }
    assert "sk-server-secret" not in res.text


def test_forwards_with_server_credential_and_model_substitution(app, monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"id": "ok"}, headers={"content-type": "application/json"})

    _install_fake_upstream(monkeypatch, handler)
    client = TestClient(app)
    res = client.post(
        "/api/llm/chat/completions?stream=false",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        json={"model": "levolia", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert res.status_code == 200
    assert res.json() == {"id": "ok"}
    assert seen["url"] == "https://upstream.example/v1/chat/completions?stream=false"
    assert seen["headers"]["authorization"] == "Bearer sk-server-secret"
    assert seen["body"]["model"] == "server/model-x"
    # The client's own token must never reach the provider.
    assert TOKEN not in json.dumps(seen["headers"])


def test_explicit_model_is_preserved(app, monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={})

    _install_fake_upstream(monkeypatch, handler)
    TestClient(app).post(
        "/api/llm/chat/completions",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={"model": "other/model", "messages": []},
    )
    assert seen["body"]["model"] == "other/model"


def test_anthropic_mode_uses_x_api_key(app, monkeypatch):
    monkeypatch.setattr(
        levolia_relay,
        "_resolve_upstream",
        lambda: {
            "provider": "anthropic",
            "api_mode": "anthropic_messages",
            "base_url": "https://api.anthropic.com",
            "api_key": "sk-ant-secret",
        },
    )
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = dict(request.headers)
        return httpx.Response(200, json={})

    _install_fake_upstream(monkeypatch, handler)
    res = TestClient(app).post(
        "/api/llm/v1/messages",
        headers={"Authorization": f"Bearer {TOKEN}", "anthropic-version": "2023-06-01"},
        json={"model": "auto", "messages": []},
    )
    assert res.status_code == 200
    assert seen["headers"]["x-api-key"] == "sk-ant-secret"
    assert seen["headers"]["anthropic-version"] == "2023-06-01"
    assert "authorization" not in seen["headers"]


def test_unreachable_upstream_returns_502(app, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    _install_fake_upstream(monkeypatch, handler)
    res = TestClient(app).post(
        "/api/llm/chat/completions",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={"model": "levolia"},
    )
    assert res.status_code == 502


def test_rejects_absolute_paths(app):
    res = TestClient(app).post(
        "/api/llm/https://evil.example/x",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={},
    )
    assert res.status_code == 400
