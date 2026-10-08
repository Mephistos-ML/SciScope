# Authentication and access boundaries

HTTP transport extracts cookies, OAuth query parameters, and the client address.
Application services accept those values explicitly and do not import FastAPI,
Starlette, request/response objects, JWT libraries, or provider HTTP clients.

| Owner | Responsibilities |
| --- | --- |
| `app/models/auth.py` | Authenticated user, verified Google identity, OAuth flow values, and stable auth errors |
| `app/api/auth.py` | Cookie extraction, attributes, deletion, and frontend redirect representation |
| `app/api/client.py` | HTTP client-address projection for Explore |
| `app/api/routes/auth.py` | HTTP callback mapping and response delivery |
| `app/services/auth/service.py` | Session issuance/resolution/revocation, authenticated account deletion, callback proof validation, and identity-to-user orchestration |
| `app/services/search/access/service.py` | Actor classification, Turnstile requirement and failure auditing, quota and admission policy |
| `app/integrations/identity/google.py` | Google authorization URL, token exchange, JWKS access, and verified ID-token mapping |
| `app/composition/auth.py` | Bind Google client credentials, redirect URI, and the process-local JWKS client |

Services receive an already authenticated `User` from the trusted entrypoint;
client-supplied user IDs are not proof of identity. Session lookup consumes an
explicit bearer token and resolves only active, unexpired, unrevoked sessions.
Only its SHA-256 hash is persisted. Account deletion resolves that credential's
owner and removes that account's sessions through persistence.

HTTP owns session and short-lived OAuth cookie names, paths, domain, SameSite,
Secure, HttpOnly, and expiry attributes. Session issuance receives an explicit
lifetime. Logout revokes the credential before clearing its cookie.

OAuth initiation creates independent random state and nonce values. Completion
rejects denied, expired/incomplete, mismatched-state, and missing-code callbacks
before provider IO. The Google capability verifies the RS256 signature, audience,
issuer, expiration, nonce, subject, and verified email before returning an identity.
Required token claims cannot be absent. Token responses are bounded to 64 KiB;
token exchange and JWKS fetches have 15-second timeouts, without automatic retries.

The HTTP callback is an intentional isolation boundary: expected OAuth rejection
returns a frontend `authError` code; unexpected failures are logged and
return `google_auth_failed`. Both callback success and rejection clear state/nonce
cookies. No session cookie is issued before durable session creation succeeds.
Missing auth deployment configuration maps to HTTP 503. Cookie-backed flow
credentials are browser-scoped; this contract does not claim durable one-time
consumption of callback state across simultaneous requests.

Explore receives explicit user/client-address facts. Suspicious-actor proof
verification and denial auditing happen in the service before the locked
admission transaction. External verification does not run while holding admission
locks. Search-run reads and expansion require owner identity or the guest token.
Deployment must establish trusted forwarding before treating the projected client
address as an abuse signal.
An IP address never authorizes access to a user-owned resource.

Tests exercise session hash/expiry/revocation, account ownership, callback guards,
real JWT signatures with external IO mocked, cookie delivery/cleanup, and
search access journeys. Routine tests do not contact live Google services.

[Google's OIDC validation contract](https://developers.google.com/identity/openid-connect/openid-connect)
provides the provider requirements for token verification.
