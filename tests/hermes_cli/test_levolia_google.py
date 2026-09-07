"""Tests for the Levolia Google connection endpoints."""
from __future__ import annotations

import subprocess

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hermes_cli import levolia_google


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(levolia_google, "_hermes_home", lambda: tmp_path)
    script = tmp_path / "setup.py"
    script.write_text("# stub\n")
    monkeypatch.setattr(levolia_google, "_setup_script", lambda: script)
    application = FastAPI()
    application.include_router(levolia_google.router)
    return application


def _completed(args, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args, returncode, stdout, stderr)


def test_status_unavailable_without_client_secret(app):
    res = TestClient(app).get("/api/levolia/google/status")
    assert res.status_code == 200
    assert res.json()["available"] is False
    assert res.json()["authorized"] is False


def test_status_reports_authorized_from_check(app, tmp_path, monkeypatch):
    (tmp_path / "google_client_secret.json").write_text("{}")
    monkeypatch.setattr(levolia_google, "_run_setup", lambda args: _completed(args, 0, "AUTHENTICATED: ok"))
    res = TestClient(app).get("/api/levolia/google/status")
    assert res.json() == {"available": True, "authorized": True, "detail": "AUTHENTICATED: ok"}


def test_status_not_authorized(app, tmp_path, monkeypatch):
    (tmp_path / "google_client_secret.json").write_text("{}")
    monkeypatch.setattr(levolia_google, "_run_setup", lambda args: _completed(args, 1, "NOT_AUTHENTICATED: no token"))
    body = TestClient(app).get("/api/levolia/google/status").json()
    assert body["available"] is True and body["authorized"] is False


def test_auth_url_returns_last_https_line(app, monkeypatch):
    seen = {}

    def fake(args):
        seen["args"] = args
        return _completed(args, 0, "Visit this URL:\nhttps://accounts.google.com/o/oauth2/auth?x=1\n")

    monkeypatch.setattr(levolia_google, "_run_setup", fake)
    res = TestClient(app).post("/api/levolia/google/auth-url")
    assert res.status_code == 200
    assert res.json() == {"url": "https://accounts.google.com/o/oauth2/auth?x=1"}
    assert seen["args"] == ["--auth-url"]


def test_auth_url_failure_is_502(app, monkeypatch):
    monkeypatch.setattr(levolia_google, "_run_setup", lambda args: _completed(args, 1, "ERROR: No client secret stored."))
    res = TestClient(app).post("/api/levolia/google/auth-url")
    assert res.status_code == 502
    assert "No client secret" in res.json()["detail"]


def test_auth_code_exchanges(app, monkeypatch):
    seen = {}

    def fake(args):
        seen["args"] = args
        return _completed(args, 0, "OK: Authenticated.")

    monkeypatch.setattr(levolia_google, "_run_setup", fake)
    res = TestClient(app).post("/api/levolia/google/auth-code", json={"code": "4/abc"})
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert seen["args"] == ["--auth-code", "4/abc"]


def test_auth_code_requires_code(app):
    assert TestClient(app).post("/api/levolia/google/auth-code", json={"code": "  "}).status_code == 400


def test_auth_code_failure_is_502(app, monkeypatch):
    monkeypatch.setattr(levolia_google, "_run_setup", lambda args: _completed(args, 1, "ERROR: Token exchange failed"))
    res = TestClient(app).post("/api/levolia/google/auth-code", json={"code": "bad"})
    assert res.status_code == 502
    assert res.json()["ok"] is False
