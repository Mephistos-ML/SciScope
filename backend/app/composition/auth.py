"""Select and configure the identity provider at the API entrypoint."""

from jwt import PyJWKClient

from app import config
from app.integrations.identity.google import GoogleOAuthClient, GOOGLE_JWKS_URL
from app.services.auth.service import GoogleOAuth


def build_google_oauth() -> GoogleOAuth:
    return GoogleOAuthClient(
        config.GOOGLE_CLIENT_ID, config.GOOGLE_CLIENT_SECRET,
        config.GOOGLE_OAUTH_REDIRECT_URI, PyJWKClient(GOOGLE_JWKS_URL, timeout=15),
    )
