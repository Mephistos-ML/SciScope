# Frontend

React + TypeScript dashboard for SciScope.

## Local dev

1. Install Node.js 20+.
2. Run the backend API on `http://127.0.0.1:8000`.
3. From `frontend/` run:

```bash
npm install
cp .env.example .env
npm run dev
```

Set these values in `frontend/.env`:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_AUTH_MODE=dev
```

`VITE_AUTH_MODE=dev` enables the temporary developer sign-in button against the backend `POST /api/auth/dev-login` endpoint. For any public deployment, keep `VITE_AUTH_MODE=disabled` until the real authentication flow lands.

Backend entrypoint:

```bash
cd /Users/ernestborysenko/git/SciScope
./.venv/bin/python -m app.main
```

## Production deploy

Recommended hosting split:

- frontend: Vercel
- backend API: Fly.io

For Vercel:

1. Import the repository.
2. Set the project root to `frontend/`.
3. Set `VITE_API_BASE_URL` to the public backend URL, for example `https://api.sciscope.uk`.
4. Set `VITE_AUTH_MODE=disabled` until Google sign-in is implemented.
5. Deploy from the `main` branch for production and from feature branches for preview environments.
