"""Lightweight HMAC-signed cookie authentication gate for public Cloud Run Web UI deployments.

When ``UI_AUTH_SECRET_ID`` (Google Secret Manager) or ``UI_ACCESS_TOKEN`` (local dev/tests)
is configured, every ``/api/*`` endpoint (except auth endpoints) requires a valid
``HttpOnly`` HMAC-SHA256 session cookie obtained via ``POST /api/auth/login``.

When neither is configured (e.g. local workstation use), authentication is disabled.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from collections import defaultdict, deque

from fastapi import Request, Response

from bacen_advisor.config import is_managed_runtime
from bacen_advisor.secrets import SecretNotFoundError, get_secret

SESSION_COOKIE_NAME = "bacen_ui_session"
SESSION_TTL_SECONDS = 12 * 60 * 60  # 12 hours
_RATE_LIMIT_MAX_FAILURES = 8
_RATE_LIMIT_WINDOW_SECONDS = 10 * 60


class AccessGate:
    """Stateless HMAC session cookie verifier with per-IP login failure rate limiting."""

    def __init__(self, *, access_token: str | None = None, enabled_override: bool | None = None) -> None:
        self._explicit_token = access_token
        self._enabled_override = enabled_override
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _resolve_token(self) -> str | None:
        if self._enabled_override is False:
            return None
        if self._explicit_token is not None:
            return self._explicit_token.strip() or None

        secret_id = os.getenv("UI_AUTH_SECRET_ID", "").strip()
        env_token = os.getenv("UI_ACCESS_TOKEN", "").strip()
        if not secret_id and not env_token:
            return None

        if secret_id:
            try:
                resolved = get_secret(secret_id, env_override="UI_ACCESS_TOKEN").strip()
                if resolved:
                    return resolved
            except SecretNotFoundError:
                if is_managed_runtime():
                    raise
        if env_token and not is_managed_runtime():
            return env_token
        return None

    @property
    def enabled(self) -> bool:
        return self._resolve_token() is not None

    def _signing_key(self, token: str) -> bytes:
        return hashlib.sha256(f"bacen-ui-hmac-v1:{token}".encode()).digest()

    def _token_digest(self, token: str) -> bytes:
        return hashlib.sha256(token.encode("utf-8")).digest()

    def is_rate_limited(self, client_ip: str) -> bool:
        now = time.time()
        bucket = self._failures[client_ip]
        while bucket and now - bucket[0] > _RATE_LIMIT_WINDOW_SECONDS:
            bucket.popleft()
        return len(bucket) >= _RATE_LIMIT_MAX_FAILURES

    def record_failure(self, client_ip: str) -> None:
        now = time.time()
        bucket = self._failures[client_ip]
        bucket.append(now)
        if len(self._failures) > 5_000:
            self._failures.clear()

    def clear_failures(self, client_ip: str) -> None:
        self._failures.pop(client_ip, None)

    def verify_password(self, candidate: str) -> bool:
        expected = self._resolve_token()
        if not expected:
            return True
        return hmac.compare_digest(
            self._token_digest(candidate.strip()),
            self._token_digest(expected),
        )

    def create_session_cookie(self, *, ttl_seconds: int = SESSION_TTL_SECONDS) -> str:
        expected = self._resolve_token()
        if not expected:
            return ""
        exp = int(time.time()) + ttl_seconds
        payload = f"v1.{exp}"
        sig = hmac.new(self._signing_key(expected), payload.encode("ascii"), hashlib.sha256).hexdigest()
        return f"{payload}.{sig}"

    def is_authenticated(self, request: Request) -> bool:
        expected = self._resolve_token()
        if not expected:
            return True
        cookie = request.cookies.get(SESSION_COOKIE_NAME, "")
        if not cookie:
            return False
        parts = cookie.split(".")
        if len(parts) != 3 or parts[0] != "v1":
            return False
        try:
            exp = int(parts[1])
        except ValueError:
            return False
        if exp < int(time.time()):
            return False
        payload = f"{parts[0]}.{parts[1]}"
        expected_sig = hmac.new(
            self._signing_key(expected), payload.encode("ascii"), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(parts[2], expected_sig)

    def set_cookie(self, response: Response, request: Request) -> None:
        value = self.create_session_cookie()
        is_https = (
            is_managed_runtime()
            or request.url.scheme == "https"
            or request.headers.get("x-forwarded-proto", "").lower() == "https"
        )
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=value,
            max_age=SESSION_TTL_SECONDS,
            httponly=True,
            secure=is_https,
            samesite="lax",
            path="/",
        )

    def clear_cookie(self, response: Response) -> None:
        response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
