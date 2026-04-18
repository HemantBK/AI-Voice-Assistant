"""Minimal API-key gate. Opt-in via `API_KEY` env var — when unset, auth
is bypassed (useful for local dev). When set, every HTTP request and
WebSocket handshake must present the key via:
  - Header:  `X-API-Key: <value>` (preferred)
  - Query:   `?api_key=<value>` (fallback; WS handshakes can't add headers
              from the browser without tricks, so we accept query too)
"""
from __future__ import annotations

import logging
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import API_KEY

logger = logging.getLogger(__name__)

_EXEMPT_PATHS = {"/", "/health", "/ready", "/docs", "/redoc", "/openapi.json"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not API_KEY:
            return await call_next(request)
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        supplied = request.headers.get("x-api-key") or request.query_params.get("api_key", "")
        if not supplied or not secrets.compare_digest(supplied, API_KEY):
            logger.warning("auth.failed path=%s", request.url.path)
            return JSONResponse(status_code=401, content={"detail": "invalid or missing API key"})
        return await call_next(request)


async def require_api_key_ws(websocket) -> bool:
    """Gate a WebSocket handshake. Returns True on accept, False if the
    handshake was rejected (caller should return immediately)."""
    if not API_KEY:
        return True
    supplied = websocket.headers.get("x-api-key") or websocket.query_params.get("api_key", "")
    if not supplied or not secrets.compare_digest(supplied, API_KEY):
        await websocket.close(code=1008, reason="invalid api key")
        return False
    return True
