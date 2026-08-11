"""Cookie-backed authentication helpers and Google OAuth flow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
import secrets
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request as UrlRequest, urlopen

import jwt
from jwt import PyJWKClient

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from app.config import (
    AUTH_SESSION_COOKIE_DOMAIN,
    AUTH_SESSION_COOKIE_NAME,
    AUTH_SESSION_SAMESITE,
    AUTH_SESSION_SECURE,
    AUTH_SESSION_TTL_SECONDS,
    FRONTEND_BASE_URL,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_OAUTH_REDIRECT_URI,
)
from app.storage.auth import (
    create_user_session,
    create_oauth_account,
    create_user,
    get_authenticated_session_by_token_hash,
    get_oauth_account_by_provider_subject,
    get_user_by_email,
    revoke_user_session_by_token_hash,
    touch_user_session,
    update_oauth_account,
    update_user,
)

GOOGLE_PROVIDER = "google"
GOOGLE_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_SCOPES = "openid email profile"
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")
GOOGLE_OAUTH_FLOW_TTL_SECONDS = 600
GOOGLE_OAUTH_STATE_COOKIE_NAME = f"{AUTH_SESSION_COOKIE_NAME}_google_state"
GOOGLE_OAUTH_NONCE_COOKIE_NAME = f"{AUTH_SESSION_COOKIE_NAME}_google_nonce"
_GOOGLE_JWK_CLIENT = PyJWKClient(GOOGLE_JWKS_URL)


@dataclass(frozen=True)
class User:
    """Minimal authenticated viewer projection."""

    user_id: str
    email: str
    display_name: str
    avatar_url: str | None = None


@dataclass(frozen=True)
class GoogleIdentity:
    """Normalized Google OIDC identity payload."""

    subject: str
    email: str
    display_name: str
    avatar_url: str | None


def get_current_user(request: Request) -> User | None:
    """Resolve the signed-in user from the current session cookie."""

    session_record = _get_authenticated_session(request)
    if session_record is None:
        return None

    touch_user_session(session_record.session.session_id)
    return User(
        user_id=session_record.user.user_id,
        email=session_record.user.email,
        display_name=session_record.user.display_name,
        avatar_url=session_record.user.avatar_url,
    )


def create_authenticated_session(user_id: str, response: Response) -> str:
    """Create one durable session and attach its cookie to the response."""

    session_token = secrets.token_urlsafe(48)
    create_user_session(
        user_id=user_id,
        session_token_hash=_hash_session_token(session_token),
        expires_at=_utc_now() + timedelta(seconds=AUTH_SESSION_TTL_SECONDS),
    )
    _set_session_cookie(response, session_token)
    return session_token


def build_google_auth_redirect_response() -> RedirectResponse:
    """Begin one Google OAuth flow and redirect the browser to Google."""

    _require_google_oauth_config()
    state_token = secrets.token_urlsafe(32)
    nonce_token = secrets.token_urlsafe(32)
    query = urlencode(
        {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": GOOGLE_OAUTH_REDIRECT_URI,
            "response_type": "code",
            "scope": GOOGLE_SCOPES,
            "state": state_token,
            "nonce": nonce_token,
            "prompt": "select_account",
        }
    )
    response = RedirectResponse(
        url=f"{GOOGLE_AUTHORIZATION_URL}?{query}",
        status_code=status.HTTP_302_FOUND,
    )
    _set_short_lived_cookie(response, GOOGLE_OAUTH_STATE_COOKIE_NAME, state_token)
    _set_short_lived_cookie(response, GOOGLE_OAUTH_NONCE_COOKIE_NAME, nonce_token)
    return response


def complete_google_auth_callback(request: Request) -> RedirectResponse:
    """Finish Google OAuth, attach a first-party session, and return to the frontend."""

    _require_google_oauth_config()
    expected_state = _read_flow_cookie(request, GOOGLE_OAUTH_STATE_COOKIE_NAME)
    expected_nonce = _read_flow_cookie(request, GOOGLE_OAUTH_NONCE_COOKIE_NAME)
    google_error = request.query_params.get("error", "").strip()
    returned_state = request.query_params.get("state", "").strip()
    authorization_code = request.query_params.get("code", "").strip()

    if google_error:
        return _build_frontend_auth_redirect(error="google_access_denied")

    if not expected_state or not expected_nonce:
        return _build_frontend_auth_redirect(error="google_session_expired")

    if returned_state != expected_state:
        return _build_frontend_auth_redirect(error="google_state_mismatch")

    if not authorization_code:
        return _build_frontend_auth_redirect(error="google_missing_code")

    try:
        token_payload = _exchange_google_code_for_tokens(authorization_code)
        identity = _verify_google_identity(
            token_payload["id_token"],
            expected_nonce=expected_nonce,
        )
        response = _build_frontend_auth_redirect()
        user = upsert_google_user(identity)
        create_authenticated_session(user.user_id, response)
        return response
    except Exception:
        return _build_frontend_auth_redirect(error="google_auth_failed")


def upsert_google_user(identity: GoogleIdentity) -> User:
    """Create or refresh one first-party user from a Google identity."""

    oauth_account = get_oauth_account_by_provider_subject(
        GOOGLE_PROVIDER,
        identity.subject,
    )

    if oauth_account is not None:
        user_record = update_user(
            oauth_account.user_id,
            email=identity.email,
            display_name=identity.display_name,
            avatar_url=identity.avatar_url,
        )
        update_oauth_account(
            oauth_account.oauth_account_id,
            provider_email=identity.email,
        )
        return _to_user(user_record)

    existing_user = get_user_by_email(identity.email)
    if existing_user is not None:
        user_record = update_user(
            existing_user.user_id,
            email=identity.email,
            display_name=identity.display_name,
            avatar_url=identity.avatar_url,
        )
    else:
        user_record = create_user(
            email=identity.email,
            display_name=identity.display_name,
            avatar_url=identity.avatar_url,
        )

    create_oauth_account(
        user_id=user_record.user_id,
        provider=GOOGLE_PROVIDER,
        provider_subject=identity.subject,
        provider_email=identity.email,
    )
    return _to_user(user_record)


def sign_out_current_user(request: Request, response: Response) -> None:
    """Revoke the current session cookie if present and clear the browser cookie."""

    session_token = _read_session_token(request)
    if session_token:
        revoke_user_session_by_token_hash(_hash_session_token(session_token))
    _clear_session_cookie(response)


def _get_authenticated_session(request: Request):
    session_token = _read_session_token(request)
    if not session_token:
        return None
    return get_authenticated_session_by_token_hash(_hash_session_token(session_token))


def _read_session_token(request: Request) -> str | None:
    raw_value = request.cookies.get(AUTH_SESSION_COOKIE_NAME, "").strip()
    if not raw_value:
        return None
    return raw_value


def _read_flow_cookie(request: Request, cookie_name: str) -> str | None:
    raw_value = request.cookies.get(cookie_name, "").strip()
    if not raw_value:
        return None
    return raw_value


def _hash_session_token(session_token: str) -> str:
    return hashlib.sha256(session_token.encode("utf-8")).hexdigest()


def _set_session_cookie(response: Response, session_token: str) -> None:
    response.set_cookie(
        key=AUTH_SESSION_COOKIE_NAME,
        value=session_token,
        max_age=AUTH_SESSION_TTL_SECONDS,
        httponly=True,
        secure=AUTH_SESSION_SECURE,
        samesite=AUTH_SESSION_SAMESITE,
        path="/",
        domain=AUTH_SESSION_COOKIE_DOMAIN or None,
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=AUTH_SESSION_COOKIE_NAME,
        httponly=True,
        secure=AUTH_SESSION_SECURE,
        samesite=AUTH_SESSION_SAMESITE,
        path="/",
        domain=AUTH_SESSION_COOKIE_DOMAIN or None,
    )


def _set_short_lived_cookie(response: Response, cookie_name: str, value: str) -> None:
    response.set_cookie(
        key=cookie_name,
        value=value,
        max_age=GOOGLE_OAUTH_FLOW_TTL_SECONDS,
        httponly=True,
        secure=AUTH_SESSION_SECURE,
        samesite=AUTH_SESSION_SAMESITE,
        path="/",
        domain=AUTH_SESSION_COOKIE_DOMAIN or None,
    )


def _clear_short_lived_cookie(response: Response, cookie_name: str) -> None:
    response.delete_cookie(
        key=cookie_name,
        httponly=True,
        secure=AUTH_SESSION_SECURE,
        samesite=AUTH_SESSION_SAMESITE,
        path="/",
        domain=AUTH_SESSION_COOKIE_DOMAIN or None,
    )


def _build_frontend_auth_redirect(*, error: str | None = None) -> RedirectResponse:
    frontend_base_url = _require_google_oauth_config()["frontend_base_url"]
    redirect_url = frontend_base_url
    if error is not None:
        parts = urlsplit(frontend_base_url)
        redirect_url = urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode({"authError": error}),
                "",
            )
        )

    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
    _clear_short_lived_cookie(response, GOOGLE_OAUTH_STATE_COOKIE_NAME)
    _clear_short_lived_cookie(response, GOOGLE_OAUTH_NONCE_COOKIE_NAME)
    return response


def _exchange_google_code_for_tokens(authorization_code: str) -> dict[str, object]:
    encoded_body = urlencode(
        {
            "code": authorization_code,
            "client_id": _require_google_oauth_config()["client_id"],
            "client_secret": _require_google_oauth_config()["client_secret"],
            "redirect_uri": _require_google_oauth_config()["redirect_uri"],
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    request = UrlRequest(
        GOOGLE_TOKEN_URL,
        data=encoded_body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if "id_token" not in payload:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google token exchange did not return an ID token",
        )
    return payload


def _verify_google_identity(id_token: str, *, expected_nonce: str) -> GoogleIdentity:
    signing_key = _GOOGLE_JWK_CLIENT.get_signing_key_from_jwt(id_token)
    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=_require_google_oauth_config()["client_id"],
        issuer=GOOGLE_ISSUERS,
    )

    if claims.get("nonce") != expected_nonce:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google nonce verification failed",
        )

    email = str(claims.get("email", "")).strip().lower()
    subject = str(claims.get("sub", "")).strip()
    if not subject or not email or claims.get("email_verified") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google identity is missing required verified email data",
        )

    display_name = str(claims.get("name", "")).strip() or email
    avatar_url = str(claims.get("picture", "")).strip() or None
    return GoogleIdentity(
        subject=subject,
        email=email,
        display_name=display_name,
        avatar_url=avatar_url,
    )


def _require_google_oauth_config() -> dict[str, str]:
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured: missing GOOGLE_CLIENT_ID",
        )
    if not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured: missing GOOGLE_CLIENT_SECRET",
        )
    if not GOOGLE_OAUTH_REDIRECT_URI:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured: missing GOOGLE_OAUTH_REDIRECT_URI",
        )
    if not FRONTEND_BASE_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured: missing FRONTEND_BASE_URL",
        )

    return {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_OAUTH_REDIRECT_URI,
        "frontend_base_url": FRONTEND_BASE_URL.rstrip("/"),
    }


def _to_user(user_record) -> User:
    return User(
        user_id=user_record.user_id,
        email=user_record.email,
        display_name=user_record.display_name,
        avatar_url=user_record.avatar_url,
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)
