"""Google OAuth token exchange and OIDC signature/claim verification."""

from dataclasses import dataclass, field
import json
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest, urlopen

import jwt
from jwt import PyJWKClient

from app.models.auth import GoogleIdentity, GoogleAuthError, AuthConfigurationError

GOOGLE_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_SCOPES = "openid email profile"
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")

@dataclass(frozen=True)
class GoogleOAuthClient:
    client_id: str
    client_secret: str = field(repr=False)
    redirect_uri: str
    jwk_client: PyJWKClient = field(repr=False)

    def _require_config(self) -> None:
        for name, value in (("GOOGLE_CLIENT_ID", self.client_id), ("GOOGLE_CLIENT_SECRET", self.client_secret), ("GOOGLE_OAUTH_REDIRECT_URI", self.redirect_uri)):
            if not value:
                raise AuthConfigurationError(f"Google OAuth is not configured: missing {name}")

    def authorization_url(self, *, state: str, nonce: str) -> str:
        self._require_config()
        return GOOGLE_AUTHORIZATION_URL + "?" + urlencode({
            "client_id": self.client_id, "redirect_uri": self.redirect_uri,
            "response_type": "code", "scope": GOOGLE_SCOPES,
            "state": state, "nonce": nonce, "prompt": "select_account",
        })

    def authenticate(self, code: str, *, expected_nonce: str) -> GoogleIdentity:
        self._require_config()
        try:
            payload = self._exchange_google_code_for_tokens(code)
            return self._verify_google_identity(payload["id_token"], expected_nonce=expected_nonce)
        except (OSError, ValueError, jwt.PyJWTError) as exc:
            raise GoogleAuthError("google_auth_failed") from exc

    def _exchange_google_code_for_tokens(self, authorization_code: str) -> dict[str, object]:
        encoded_body = urlencode(
            {
                "code": authorization_code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
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
            raw = response.read(65537)
            if len(raw) > 65536:
                raise GoogleAuthError("google_auth_failed")
            payload = json.loads(raw.decode("utf-8"))

        if not isinstance(payload, dict) or not isinstance(payload.get("id_token"), str) or not payload["id_token"].strip():
            raise GoogleAuthError("google_auth_failed")
        return payload


    def _verify_google_identity(self, id_token: str, *, expected_nonce: str) -> GoogleIdentity:
        signing_key = self.jwk_client.get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=self.client_id,
            issuer=GOOGLE_ISSUERS,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )

        if claims.get("nonce") != expected_nonce:
            raise GoogleAuthError("google_auth_failed")

        if not isinstance(claims.get("email"), str) or not isinstance(claims.get("sub"), str):
            raise GoogleAuthError("google_auth_failed")
        email = claims["email"].strip().lower()
        subject = claims["sub"].strip()
        if not subject or not email or claims.get("email_verified") is not True:
            raise GoogleAuthError("google_auth_failed")

        name, picture = claims.get("name"), claims.get("picture")
        if any(value is not None and not isinstance(value, str) for value in (name, picture)):
            raise GoogleAuthError("google_auth_failed")
        display_name = (name or "").strip() or email
        avatar_url = (picture or "").strip() or None
        return GoogleIdentity(
            subject=subject,
            email=email,
            display_name=display_name,
            avatar_url=avatar_url,
        )
