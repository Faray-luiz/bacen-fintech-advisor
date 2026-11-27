"""Authentication & Admin Allowlist gate for Cloud Run Web UI.

Supports:
* **Google Sign-In (Google Identity Services OIDC ID token)** verified cryptographically
  via ``google.oauth2.id_token.verify_oauth2_token``.
* **Secret Manager Email/Domain Allowlist** (``UI_ALLOWED_EMAILS_SECRET_ID``, default
  ``bacen-ui-allowed-emails``) with 60-second TTL cache, instant invalidation on admin
  edits, and live session revocation.
* **Admin Panel Authorization** (``UI_ADMIN_EMAILS``): designated admins can grant and
  revoke emails or ``@domain`` rules directly from the Web UI; admins are protected
  against accidental self-lockout and changes persist durably to Google Secret Manager.
* **Optional Access-Token Fallback** (``UI_AUTH_SECRET_ID`` / ``UI_ACCESS_TOKEN``).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import Request, Response

from bacen_advisor.config import get_settings, is_managed_runtime
from bacen_advisor.secrets import SecretNotFoundError, get_secret

SESSION_COOKIE_NAME = "bacen_ui_session"
SESSION_TTL_SECONDS = 12 * 60 * 60  # 12 hours
_ALLOWLIST_TTL_SECONDS = 60.0
_RATE_LIMIT_MAX_FAILURES = 8
_RATE_LIMIT_WINDOW_SECONDS = 10 * 60

_EMAIL_RE = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$")
_DOMAIN_RE = re.compile(r"^@[a-z0-9.-]+\.[a-z]{2,}$")


@dataclass(frozen=True)
class AuthenticatedUser:
    """Verified user identity extracted from a signed session cookie."""

    user_id: str
    email: str = ""
    name: str = ""
    picture: str = ""
    auth_method: str = "token"


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _user_id_from_email(email: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_.-]", "_", email.strip().lower())
    return clean[:64] or "google_user"


def validate_allowlist_entry(raw_entry: str) -> str:
    """Validates and normalizes an email address or ``@domain`` rule."""
    clean = (raw_entry or "").strip().lower()
    if _EMAIL_RE.match(clean) or _DOMAIN_RE.match(clean):
        return clean
    raise ValueError(
        "Formato inválido. Informe um e-mail completo (ex.: nome@gmail.com) "
        "ou um domínio iniciado por @ (ex.: @empresa.com)."
    )


def _parse_allowlist(raw: str) -> tuple[set[str], set[str]]:
    """Parses exact emails and ``@domain`` rules from newline/comma/semicolon-separated text."""
    emails: set[str] = set()
    domains: set[str] = set()
    for line in re.split(r"[\n,;]+", raw or ""):
        entry = line.split("#", 1)[0].strip().lower()
        if not entry:
            continue
        if _DOMAIN_RE.match(entry):
            domains.add(entry)
        elif _EMAIL_RE.match(entry):
            emails.add(entry)
    return emails, domains


def _serialize_allowlist(emails: set[str], domains: set[str]) -> str:
    entries = sorted(domains) + sorted(emails)
    return "\n".join(entries) + ("\n" if entries else "")


def _fetch_secret_uncached(secret_id: str) -> str:
    """Reads latest Secret Manager version without permanent lru_cache (supports live revocation)."""
    from google.cloud import secretmanager

    project_id = get_settings().project_id
    if not project_id:
        raise SecretNotFoundError("GOOGLE_CLOUD_PROJECT is not set.")
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    return client.access_secret_version(request={"name": name}).payload.data.decode("utf-8").strip()


def _write_secret_version(secret_id: str, payload: str) -> None:
    """Writes a new durable version of ``secret_id`` in Google Secret Manager."""
    from google.cloud import secretmanager

    project_id = get_settings().project_id
    if not project_id:
        raise SecretNotFoundError("GOOGLE_CLOUD_PROJECT is not set.")
    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{project_id}/secrets/{secret_id}"
    client.add_secret_version(
        request={"parent": parent, "payload": {"data": payload.encode("utf-8")}}
    )


def _verify_google_id_token_default(credential: str, client_id: str) -> dict[str, Any]:
    """Cryptographically verifies a Google Identity Services JWT against Google public keys."""
    import google.auth.transport.requests
    import google.oauth2.id_token

    request_adapter = google.auth.transport.requests.Request()
    return dict(
        google.oauth2.id_token.verify_oauth2_token(
            credential,
            request_adapter,
            audience=client_id,
        )
    )


class AccessGate:
    """Supports Google Sign-In (OIDC + Secret Manager allowlist), Admin Panel & token fallback."""

    def __init__(
        self,
        *,
        access_token: str | None = None,
        google_client_id: str | None = None,
        allowed_emails: list[str] | None = None,
        admin_emails: list[str] | None = None,
        allow_token_login: bool | None = None,
        google_verifier: Callable[[str, str], dict[str, Any]] | None = None,
        enabled_override: bool | None = None,
    ) -> None:
        self._explicit_token = access_token
        self._explicit_google_client_id = google_client_id
        self._explicit_allowed_emails = allowed_emails
        self._explicit_admin_emails = admin_emails
        self._allow_token_login_override = allow_token_login
        self._google_verifier = google_verifier or _verify_google_id_token_default
        self._enabled_override = enabled_override
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._allowlist_cache: tuple[float, set[str], set[str]] | None = None
        self._allowlist_lock = threading.Lock()

    def _resolve_google_client_id(self) -> str | None:
        if self._enabled_override is False:
            return None
        if self._explicit_google_client_id is not None:
            return self._explicit_google_client_id.strip() or None
        val = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
        return val or None

    def _resolve_admin_emails(self) -> set[str]:
        if self._explicit_admin_emails is not None:
            emails, _ = _parse_allowlist("\n".join(self._explicit_admin_emails))
            return emails
        raw = os.getenv("UI_ADMIN_EMAILS", "").strip()
        emails, _ = _parse_allowlist(raw)
        return emails

    def _resolve_signing_secret(self) -> str | None:
        if self._enabled_override is False:
            return None
        if self._explicit_token is not None:
            return self._explicit_token.strip() or None

        secret_id = os.getenv("UI_AUTH_SECRET_ID", "").strip()
        env_token = os.getenv("UI_ACCESS_TOKEN", "").strip()
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

    def _resolve_allowlist(self, *, force_refresh: bool = False) -> tuple[set[str], set[str]]:
        if self._explicit_allowed_emails is not None:
            return _parse_allowlist("\n".join(self._explicit_allowed_emails))

        with self._allowlist_lock:
            now = time.monotonic()
            if (
                not force_refresh
                and self._allowlist_cache
                and (now - self._allowlist_cache[0]) < _ALLOWLIST_TTL_SECONDS
            ):
                return set(self._allowlist_cache[1]), set(self._allowlist_cache[2])

            env_list = os.getenv("UI_ALLOWED_EMAILS", "").strip()
            secret_id = os.getenv("UI_ALLOWED_EMAILS_SECRET_ID", "").strip()
            raw = ""
            if env_list and not is_managed_runtime():
                raw = env_list
            elif secret_id:
                try:
                    raw = _fetch_secret_uncached(secret_id)
                except Exception:  # noqa: BLE001
                    if self._allowlist_cache:
                        return set(self._allowlist_cache[1]), set(self._allowlist_cache[2])
                    raw = ""
            elif env_list:
                raw = env_list

            emails, domains = _parse_allowlist(raw)
            self._allowlist_cache = (now, set(emails), set(domains))
            return emails, domains

    def invalidate_allowlist_cache(self) -> None:
        with self._allowlist_lock:
            self._allowlist_cache = None

    @property
    def google_client_id(self) -> str | None:
        return self._resolve_google_client_id()

    @property
    def google_enabled(self) -> bool:
        return self._resolve_google_client_id() is not None

    @property
    def token_login_enabled(self) -> bool:
        if self._enabled_override is False:
            return False
        has_token = self._resolve_signing_secret() is not None
        if not has_token:
            return False
        if self._allow_token_login_override is not None:
            return self._allow_token_login_override
        env_flag = os.getenv("UI_ALLOW_TOKEN_LOGIN")
        if env_flag is not None:
            return env_flag.strip().lower() in {"1", "true", "yes", "on"}
        return not self.google_enabled

    @property
    def enabled(self) -> bool:
        if self._enabled_override is False:
            return False
        return self.google_enabled or self.token_login_enabled

    def is_admin(self, user: AuthenticatedUser | None) -> bool:
        if not user or not user.email or user.auth_method != "google":
            return False
        return user.email.strip().lower() in self._resolve_admin_emails()

    def get_allowlist_snapshot(self, *, force_refresh: bool = False) -> dict[str, Any]:
        emails, domains = self._resolve_allowlist(force_refresh=force_refresh)
        admins = sorted(self._resolve_admin_emails())
        secret_id = os.getenv("UI_ALLOWED_EMAILS_SECRET_ID", "").strip()
        storage = (
            "secret_manager"
            if (self._explicit_allowed_emails is None and secret_id and (is_managed_runtime() or not os.getenv("UI_ALLOWED_EMAILS")))
            else "memory"
        )
        return {
            "admins": admins,
            "emails": sorted(emails | set(admins)),
            "domains": sorted(domains),
            "storage": storage,
            "secret_id": secret_id if storage == "secret_manager" else None,
        }

    def _persist_allowlist(self, emails: set[str], domains: set[str]) -> None:
        if self._explicit_allowed_emails is not None:
            self._explicit_allowed_emails[:] = sorted(domains) + sorted(emails)
            return

        secret_id = os.getenv("UI_ALLOWED_EMAILS_SECRET_ID", "").strip()
        payload = _serialize_allowlist(emails, domains)
        if secret_id and (is_managed_runtime() or not os.getenv("UI_ALLOWED_EMAILS")):
            _write_secret_version(secret_id, payload)
        else:
            os.environ["UI_ALLOWED_EMAILS"] = payload
        self.invalidate_allowlist_cache()

    def add_allowlist_entry(self, raw_entry: str) -> dict[str, Any]:
        entry = validate_allowlist_entry(raw_entry)
        emails, domains = self._resolve_allowlist(force_refresh=True)
        if entry.startswith("@"):
            domains.add(entry)
        else:
            emails.add(entry)
        self._persist_allowlist(emails, domains)
        return self.get_allowlist_snapshot(force_refresh=True)

    def remove_allowlist_entry(self, raw_entry: str) -> dict[str, Any]:
        entry = validate_allowlist_entry(raw_entry)
        admins = self._resolve_admin_emails()
        if entry in admins:
            raise PermissionError(
                f"'{entry}' é um administrador protegido e não pode ser removido pelo painel."
            )
        emails, domains = self._resolve_allowlist(force_refresh=True)
        emails.discard(entry)
        domains.discard(entry)
        self._persist_allowlist(emails, domains)
        return self.get_allowlist_snapshot(force_refresh=True)

    def _effective_signing_key(self) -> bytes:
        secret = self._resolve_signing_secret()
        if secret:
            return hashlib.sha256(f"bacen-ui-hmac-v2:{secret}".encode()).digest()
        client_id = self._resolve_google_client_id() or "local"
        return hashlib.sha256(f"bacen-ui-hmac-v2-google:{client_id}".encode()).digest()

    def _token_digest(self, token: str) -> bytes:
        return hashlib.sha256(token.encode("utf-8")).digest()

    def is_email_allowed(self, email: str) -> bool:
        norm = email.strip().lower()
        if not norm or "@" not in norm:
            return False
        # Admins are always permitted to prevent accidental lockout.
        if norm in self._resolve_admin_emails():
            return True
        emails, domains = self._resolve_allowlist()
        if norm in emails:
            return True
        domain = "@" + norm.split("@", 1)[1]
        return domain in domains

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
        if not self.token_login_enabled:
            return False
        expected = self._resolve_signing_secret()
        if not expected:
            return False
        return hmac.compare_digest(
            self._token_digest(candidate.strip()),
            self._token_digest(expected),
        )

    def verify_google_credential(self, credential: str) -> tuple[AuthenticatedUser | None, str]:
        """Verifies a Google ID token and checks email allowlist."""
        client_id = self._resolve_google_client_id()
        if not client_id:
            return None, "google_disabled"
        try:
            claims = self._google_verifier(credential.strip(), client_id)
        except Exception:  # noqa: BLE001
            return None, "invalid_token"

        issuer = str(claims.get("iss") or "")
        if issuer and issuer not in {"accounts.google.com", "https://accounts.google.com"}:
            return None, "invalid_issuer"
        if not claims.get("email_verified"):
            return None, "email_unverified"
        email = str(claims.get("email") or "").strip().lower()
        if not email:
            return None, "missing_email"
        if not self.is_email_allowed(email):
            return None, f"not_allowed:{email}"

        user = AuthenticatedUser(
            user_id=_user_id_from_email(email),
            email=email,
            name=str(claims.get("name") or email.split("@", 1)[0])[:80],
            picture=str(claims.get("picture") or "")[:300],
            auth_method="google",
        )
        return user, ""

    def create_session_cookie(
        self,
        user: AuthenticatedUser,
        *,
        ttl_seconds: int = SESSION_TTL_SECONDS,
    ) -> str:
        exp = int(time.time()) + ttl_seconds
        payload_dict = {
            "v": 2,
            "u": user.user_id,
            "e": user.email,
            "n": user.name,
            "p": user.picture,
            "m": user.auth_method,
            "exp": exp,
        }
        payload_b64 = _b64url_encode(json.dumps(payload_dict, separators=(",", ":")).encode("utf-8"))
        sig = hmac.new(self._effective_signing_key(), payload_b64.encode("ascii"), hashlib.sha256).hexdigest()
        return f"v2.{payload_b64}.{sig}"

    def get_authenticated_user(self, request: Request) -> AuthenticatedUser | None:
        if not self.enabled:
            return AuthenticatedUser(user_id="default_user", auth_method="none")
        cookie = request.cookies.get(SESSION_COOKIE_NAME, "")
        if not cookie:
            return None
        parts = cookie.split(".")
        if len(parts) != 3 or parts[0] != "v2":
            return None
        payload_b64, sig = parts[1], parts[2]
        expected_sig = hmac.new(
            self._effective_signing_key(), payload_b64.encode("ascii"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        try:
            data = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        except Exception:  # noqa: BLE001
            return None
        if int(data.get("exp") or 0) < int(time.time()):
            return None

        method = str(data.get("m") or "token")
        email = str(data.get("e") or "").strip().lower()
        if method == "google" and not self.is_email_allowed(email):
            return None
        if method == "token" and not self.token_login_enabled:
            return None

        return AuthenticatedUser(
            user_id=str(data.get("u") or "default_user"),
            email=email,
            name=str(data.get("n") or ""),
            picture=str(data.get("p") or ""),
            auth_method=method,
        )

    def is_authenticated(self, request: Request) -> bool:
        return self.get_authenticated_user(request) is not None

    def set_cookie(self, response: Response, request: Request, user: AuthenticatedUser) -> None:
        value = self.create_session_cookie(user)
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
