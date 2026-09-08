"""Levolia model relay — ``/api/llm/*``.

Lets the Levolia agent running on a client's computer use the model that is
configured on the hosted Levolia server, without any provider credential ever
leaving the server.

The client agent is configured as a plain OpenAI-compatible endpoint::

    model:
      provider: custom
      base_url: https://client.levolia.ai/api/llm
      api_mode: <mirrors the server's api_mode>
      default: <mirrors the server's model>

Every request is authenticated with the relay token (``LEVOLIA_RELAY_TOKEN``,
falling back to ``HERMES_DASHBOARD_SESSION_TOKEN``), then forwarded verbatim
to the server's currently configured provider with the server's credential
attached. Switching provider on the server therefore switches it for every
client, with no change on their computers. ``GET /api/llm/info`` tells the
client which model / api_mode to mirror.

The route is exempt from the dashboard auth gates (see
``dashboard_auth.public_paths``) because it carries its own token check:
the OAuth gate would otherwise redirect API clients to the login page.
"""
from __future__ import annotations

import hmac
import json
import logging
import os
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

logger = logging.getLogger(__name__)

router = APIRouter()

RELAY_PREFIX = "/api/llm/"
MAX_BODY_BYTES = 32 * 1024 * 1024
# Model names a client may send to mean "whatever the server is configured for".
PLACEHOLDER_MODELS = {"", "levolia", "default", "auto", "server"}

_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
    "authorization",
    "x-api-key",
    "x-hermes-session-token",
    "cookie",
}


def relay_token() -> str:
    """Return the shared secret clients must present, or '' when the relay is off."""
    for name in ("LEVOLIA_RELAY_TOKEN", "HERMES_DASHBOARD_SESSION_TOKEN"):
        value = os.environ.get(name)
        if not value:
            try:
                from hermes_cli.config import get_env_value

                value = get_env_value(name)
            except Exception:  # pragma: no cover - config layer unavailable
                value = None
        if value and value.strip():
            return value.strip()
    return ""


def _presented_token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("x-hermes-session-token", "").strip()


def _authorized(request: Request) -> Optional[JSONResponse]:
    expected = relay_token()
    if not expected:
        return JSONResponse(
            status_code=503,
            content={"detail": "Levolia relay disabled: set LEVOLIA_RELAY_TOKEN on the server."},
        )
    presented = _presented_token(request)
    if not presented or not hmac.compare_digest(presented, expected):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return None


def _server_model_config() -> Dict[str, Any]:
    from hermes_cli.config import load_config

    cfg = load_config()
    model_cfg = cfg.get("model") if isinstance(cfg, dict) else None
    if isinstance(model_cfg, dict):
        return model_cfg
    return {"default": str(model_cfg or "")}


def _resolve_upstream() -> Dict[str, Any]:
    from hermes_cli.runtime_provider import resolve_runtime_provider

    return resolve_runtime_provider()


def _upstream_auth_headers(runtime: Dict[str, Any]) -> Dict[str, str]:
    api_key = str(runtime.get("api_key") or "")
    api_mode = str(runtime.get("api_mode") or "")
    base_url = str(runtime.get("base_url") or "")
    headers: Dict[str, str] = {}

    if api_mode == "anthropic_messages":
        headers["x-api-key"] = api_key
    else:
        headers["Authorization"] = f"Bearer {api_key}"

    if api_mode == "codex_responses":
        try:
            from agent.codex_headers import codex_cloudflare_headers, is_official_codex_base_url

            if is_official_codex_base_url(base_url):
                headers.update(codex_cloudflare_headers(api_key, base_url=base_url))
        except Exception:  # pragma: no cover - optional helper
            logger.debug("codex header helper unavailable", exc_info=True)
        if "ChatGPT-Account-Id" not in headers:
            try:
                from hermes_cli.auth import _decode_jwt_claims

                claims = _decode_jwt_claims(api_key)
                auth_claims = claims.get("https://api.openai.com/auth")
                account_id = auth_claims.get("chatgpt_account_id") if isinstance(auth_claims, dict) else None
                if isinstance(account_id, str) and account_id.strip():
                    headers["ChatGPT-Account-Id"] = account_id.strip()
            except Exception:  # pragma: no cover - best effort
                logger.debug("could not derive ChatGPT-Account-Id", exc_info=True)
    return headers


def _rewrite_model(body: bytes, content_type: str, server_model: str) -> bytes:
    """Substitute the server's model when the client sent a placeholder."""
    if not server_model or "json" not in content_type.lower():
        return body
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        return body
    if not isinstance(payload, dict):
        return body
    model = payload.get("model")
    if model is None or (isinstance(model, str) and model.strip().lower() in PLACEHOLDER_MODELS):
        payload["model"] = server_model
        return json.dumps(payload).encode("utf-8")
    return body


def _make_client():
    import httpx

    return httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=30.0), follow_redirects=False)


@router.get("/api/llm/info")
async def levolia_relay_info(request: Request):
    """What a client agent must mirror to speak to this relay. No secrets."""
    denied = _authorized(request)
    if denied is not None:
        return denied
    try:
        runtime = _resolve_upstream()
    except Exception as exc:
        return JSONResponse(status_code=502, content={"detail": f"No usable model provider on the server: {exc}"})
    model_cfg = _server_model_config()
    return {
        "provider": runtime.get("provider") or model_cfg.get("provider") or "",
        "model": model_cfg.get("default") or "",
        "api_mode": runtime.get("api_mode") or model_cfg.get("api_mode") or "",
        "upstream_host": urlsplit(str(runtime.get("base_url") or "")).netloc,
    }


@router.get("/api/llm/bootstrap")
async def levolia_relay_bootstrap(request: Request):
    """Give an authenticated desktop session the relay configuration.

    Unlike the relay endpoints, this route is protected by the normal
    dashboard OAuth gate. It returns the tenant-scoped relay token, never the
    upstream provider credential, so the local agent remains usable after the
    short-lived OAuth access token expires.
    """
    if getattr(request.state, "session", None) is None:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    token = relay_token()
    if not token:
        return JSONResponse(
            status_code=503,
            content={"detail": "Levolia relay disabled: set LEVOLIA_RELAY_TOKEN on the server."},
        )

    try:
        runtime = _resolve_upstream()
    except Exception as exc:
        return JSONResponse(status_code=502, content={"detail": f"No usable model provider on the server: {exc}"})

    model_cfg = _server_model_config()
    return {
        "relay_token": token,
        "provider": runtime.get("provider") or model_cfg.get("provider") or "",
        "model": model_cfg.get("default") or "",
        "api_mode": runtime.get("api_mode") or model_cfg.get("api_mode") or "",
        "upstream_host": urlsplit(str(runtime.get("base_url") or "")).netloc,
    }


@router.api_route("/api/llm/{upstream_path:path}", methods=["GET", "POST"])
async def levolia_relay(upstream_path: str, request: Request):
    denied = _authorized(request)
    if denied is not None:
        return denied

    if not upstream_path or upstream_path.startswith(("http://", "https://", "//", "..")):
        return JSONResponse(status_code=400, content={"detail": "Invalid relay path"})

    try:
        runtime = _resolve_upstream()
    except Exception as exc:
        logger.warning("levolia relay: provider resolution failed: %s", exc)
        return JSONResponse(status_code=502, content={"detail": "No usable model provider on the server."})

    base_url = str(runtime.get("base_url") or "").rstrip("/")
    if not base_url:
        return JSONResponse(status_code=502, content={"detail": "Server model provider has no base URL."})

    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": "Request too large"})

    content_type = request.headers.get("content-type", "")
    body = _rewrite_model(body, content_type, str(_server_model_config().get("default") or ""))

    headers = {k: v for k, v in request.headers.items() if k.lower() not in _HOP_BY_HOP}
    headers.update(_upstream_auth_headers(runtime))
    headers.pop("accept-encoding", None)

    target = f"{base_url}/{upstream_path}"
    if request.url.query:
        target = f"{target}?{request.url.query}"

    client = _make_client()
    try:
        upstream_req = client.build_request(request.method, target, headers=headers, content=body)
        upstream = await client.send(upstream_req, stream=True)
    except Exception as exc:
        await client.aclose()
        logger.warning("levolia relay: upstream unreachable (%s): %s", urlsplit(target).netloc, exc)
        return JSONResponse(status_code=502, content={"detail": "Model provider unreachable from the server."})

    response_headers = {
        k: v
        for k, v in upstream.headers.items()
        if k.lower() in {"content-type", "cache-control", "x-request-id", "openai-processing-ms"}
    }

    async def _close() -> None:
        await upstream.aclose()
        await client.aclose()

    async def _body_iter():
        # Buffered responses (already read, e.g. by a test transport) cannot
        # be re-streamed; hand back their content in one chunk instead.
        if upstream.is_stream_consumed:
            yield upstream.content
            return
        async for chunk in upstream.aiter_raw():
            yield chunk

    return StreamingResponse(
        _body_iter(),
        status_code=upstream.status_code,
        headers=response_headers,
        background=BackgroundTask(_close),
    )
