# Frontend

React + TypeScript frontend for SciScope.

Use Node.js 24 and npm 11. From the repository root, run `nvm install` and `nvm use`, then
`cd frontend` and `npm ci`.

Run `npm test` for search polling lifecycle checks and `npm run build` for
TypeScript validation and the production build. Backend API tests also verify
that the client search status union matches the backend lifecycle contract.

Public service:

- `https://sciscope.uk/`

UI surfaces:

- Explore
  - public repository discovery from a topic description
- Feed
  - saved repository subscriptions for signed-in users

## Frontend Responsibility

The frontend owns:

- Explore query input and result rendering
- per-repository `Subscribe` actions
- Google sign-in entry
- subscription list and selected Feed state
- source badge links to repository URLs

## Auth Behavior

- Explore works without sign-in.
- Saving subscriptions requires Google OAuth to be configured on the backend.
- If backend Google OAuth is not configured, the frontend stays in public Explore mode.

The frontend uses:

- `VITE_API_BASE_URL`
- `VITE_API_TIMEOUT_MS`

## UX Notes

- Explore generates repository queries and shows matched repositories.
- `Subscribe` is per-result and updates the row locally to `Subscribed` after success.
- Feed focuses on saved repository subscriptions.
- The backend exposes monitoring and signal APIs.
