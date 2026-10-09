# Frontend

React + TypeScript client for SciScope. Use Node.js 24 and npm 11.
From the repository root, run `nvm install` and `nvm use`, then
`cd frontend` and `npm ci`.

```sh
npm run dev
npm test
npm run build
```

Set `VITE_API_BASE_URL` to the backend URL. `VITE_API_TIMEOUT_MS` controls request
timeouts; `VITE_TURNSTILE_SITE_KEY` enables the search challenge widget.

## Product surfaces

- Explore creates and polls searches, preserves useful results during expansion,
  and offers explicit repository subscriptions.
- Feed lists release cards and scan commit groups. Each card loads ten commit
  previews on expansion and pages additional commits on request. Opening or
  following links does not mark updates read. Card and account-wide read actions
  update server-owned state; unread badges count cards.
- My Subscriptions manages watches and previews the same grouped updates. Its
  View all updates action opens a repository-filtered Feed; All/Unread preserves
  that scope. Leaving this Feed restores the global list.
- Account provides sign-out and account deletion. Google sign-in establishes a
  backend session; user-owned Feed and subscriptions require that session.

Network calls and API errors live in `src/lib/api.ts`; transport types in
`src/types/api.ts`. `App.tsx` coordinates navigation, list scope and read actions.
`FeedUpdateCard` owns disclosure state, bounded commit pagination, cancellation
and retry feedback. Provider availability and grouping policy remain backend-owned.

Backend contract checks verify client fields, nullability and statuses against the
HTTP Feed schemas and search lifecycle. `npm test` covers search polling cleanup;
`npm run build` checks TypeScript and produces the Vite bundle. The real API and
PostgreSQL [browser journeys](e2e/README.md) cover Explore and Feed interactions.
