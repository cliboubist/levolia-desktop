"""Levolia: Google Workspace connection driven from the desktop app.

Thin, authenticated wrapper around the Google Workspace skill's setup script
(``skills/productivity/google-workspace/scripts/setup.py``) so the desktop can
offer an optional "Connect Google" step without a terminal:

    GET  /api/levolia/google/status     → {available, authorized, detail}
    POST /api/levolia/google/auth-url   → {url}
    POST /api/levolia/google/auth-code  → {ok, detail}   body: {code}
    POST /api/levolia/google/revoke     → {ok, detail}

``available`` is true once Levolia has placed the client's own Google Cloud
OAuth credentials at ``$HERMES_HOME/google_client_secret.json`` (one Google
Cloud project per client, "Desktop app" OAuth client type). Nothing here is
public: the routes sit behind the regular dashboard auth like every other
``/api/*`` endpoint.
"""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

SCRIPT_REL = Path("skills") / "productivity" / "google-workspace" / "scripts" / "setup.py"
RUN_TIMEOUT_S = 180


def _hermes_home() -> Path:
    from hermes_constants import get_hermes_home

    return Path(get_hermes_home())


def _setup_script() -> Optional[Path]:
    home_copy = _hermes_home() / SCRIPT_REL
    if home_copy.exists():
        return home_copy
    repo_copy = Path(__file__).resolve().parents[1] / SCRIPT_REL
    if repo_copy.exists():
        return repo_copy
    return None


def _interpreter() -> str:
    try:
        from hermes_cli.web_server import _dashboard_spawn_executable

        return _dashboard_spawn_executable()
    except Exception:
        return sys.executable


def _run_setup(args: List[str]) -> subprocess.CompletedProcess:
    script = _setup_script()
    if script is None:
        raise FileNotFoundError("Google Workspace skill is not installed on this agent.")
    env = dict(os.environ)
    env["HERMES_HOME"] = str(_hermes_home())
    return subprocess.run(
        [_interpreter(), str(script), *args],
        capture_output=True,
        text=True,
        timeout=RUN_TIMEOUT_S,
        env=env,
        cwd=str(script.parent),
    )


def _tail(text: str, limit: int = 600) -> str:
    text = (text or "").strip()
    return text[-limit:]


class GoogleAuthCode(BaseModel):
    code: str


@router.get("/api/levolia/google/status")
async def levolia_google_status() -> Dict[str, Any]:
    home = _hermes_home()
    available = (home / "google_client_secret.json").exists() and _setup_script() is not None
    if not available:
        return {"available": False, "authorized": False, "detail": "No Google credentials provisioned for this agent."}
    try:
        proc = await asyncio.to_thread(_run_setup, ["--check"])
    except Exception as exc:
        logger.warning("levolia google status failed: %s", exc)
        return {"available": True, "authorized": False, "detail": str(exc)}
    return {
        "available": True,
        "authorized": proc.returncode == 0,
        "detail": _tail(proc.stdout or proc.stderr),
    }


@router.post("/api/levolia/google/auth-url")
async def levolia_google_auth_url():
    try:
        proc = await asyncio.to_thread(_run_setup, ["--auth-url"])
    except Exception as exc:
        return JSONResponse(status_code=503, content={"detail": str(exc)})
    url = ""
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("https://"):
            url = line
    if proc.returncode != 0 or not url:
        return JSONResponse(
            status_code=502,
            content={"detail": _tail(proc.stdout or proc.stderr) or "Could not build the Google authorization URL."},
        )
    return {"url": url}


@router.post("/api/levolia/google/auth-code")
async def levolia_google_auth_code(body: GoogleAuthCode):
    code = (body.code or "").strip()
    if not code:
        return JSONResponse(status_code=400, content={"detail": "code is required"})
    try:
        proc = await asyncio.to_thread(_run_setup, ["--auth-code", code])
    except Exception as exc:
        return JSONResponse(status_code=503, content={"detail": str(exc)})
    ok = proc.returncode == 0
    if not ok:
        return JSONResponse(status_code=502, content={"ok": False, "detail": _tail(proc.stdout or proc.stderr)})
    return {"ok": True, "detail": _tail(proc.stdout)}


@router.post("/api/levolia/google/revoke")
async def levolia_google_revoke():
    try:
        proc = await asyncio.to_thread(_run_setup, ["--revoke"])
    except Exception as exc:
        return JSONResponse(status_code=503, content={"detail": str(exc)})
    return {"ok": proc.returncode == 0, "detail": _tail(proc.stdout or proc.stderr)}
