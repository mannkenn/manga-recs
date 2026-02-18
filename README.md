building end-to-end ml project for a manga recommendation system using data from anilist api

## Frontend

A Next.js React frontend lives in the `frontend/` directory. It provides a simple UI for the FastAPI backend and can be started with:

```bash
cd frontend && npm install && npm run dev
```

The frontend proxies `/api/recommendations` to the backend at `http://localhost:8000` by default (set `BACKEND_URL` in `.env.local` to override).


