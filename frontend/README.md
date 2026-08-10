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

Set `VITE_API_BASE_URL=http://127.0.0.1:8000` in `frontend/.env`.

Backend entrypoint:

```bash
cd /Users/mephistos/git/SciScope
./.venv/bin/python -m app.main
```
