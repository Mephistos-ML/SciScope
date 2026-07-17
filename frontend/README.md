# Frontend

React + TypeScript dashboard for SciScope.

## Local dev

1. Install Node.js 20+.
2. Run the Python backend on `http://127.0.0.1:8000`.
3. From `frontend/` run:

```bash
npm install
npm run dev
```

Vite proxies `/api` requests to the local Python backend.

Backend entrypoint:

```bash
python3 /Users/mephistos/git/SciScope/backend/app/main.py
```
