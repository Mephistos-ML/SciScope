"""Application identities, OAuth flow values, and stable authentication errors."""

from dataclasses import dataclass, field


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


@dataclass(frozen=True)
class GoogleAuthFlow:
    redirect_url: str = field(repr=False)
    state: str = field(repr=False)
    nonce: str = field(repr=False)


class AuthConfigurationError(RuntimeError):
    """Authentication deployment settings are incomplete."""


class GoogleAuthError(RuntimeError):
    """An OAuth callback cannot establish a verified identity."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)
