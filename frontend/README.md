# Manga Recs Frontend

This directory contains a simple Next.js (React) application that provides a UI for the Manga Recommendation API.

## Getting started

1. **Install dependencies**
   ```bash
   cd frontend
   npm install
   ```

2. **Run development server**
   ```bash
   npm run dev
   ```
   The app will be available at `http://localhost:3000`.

3. **Backend API**

   The frontend expects the recommendation API to be running separately (FastAPI server).
   By default it proxies through `http://localhost:8000` via the built-in Next.js API route, but you can override with an environment variable:

   ```bash
   echo "BACKEND_URL=http://localhost:8000" > .env.local
   ```

4. **Build for production**
   ```bash
   npm run build
   npm start
   ```

## Features

- Search for a manga title
- Specify how many similar titles to return (Top N)
- Displays results with similarity score, description, and tags

## Deployment

This app is deployed to Vercel with the repository **Root Directory** set to
`frontend` and `BACKEND_URL` pointing at the deployed FastAPI service. See the
top-level [`DEPLOYMENT.md`](../DEPLOYMENT.md) for full instructions.

> ⚠️ Requests are proxied server-side via `/api/recommendations`, so the browser
> never calls the backend directly. If you bypass the proxy, make sure CORS is
> configured on the backend (`MANGA_RECS_CORS_ORIGINS`).
