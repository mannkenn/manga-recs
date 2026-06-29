# Deployment

This project deploys as two pieces:

- **Backend** — the FastAPI recommendation API, deployed to **Render** as a Docker web service.
- **Frontend** — the Next.js app in `frontend/`, deployed to **Vercel**.

The frontend talks to the backend through its own server-side proxy route
(`/api/recommendations`), so the browser never calls the backend directly.

```
Browser ──> Vercel (Next.js)  ──>  Render (FastAPI)  ──>  AWS S3 (model + metadata)
             /api/recommendations    /recommendations/
```

## Prerequisites

- The trained similarity matrix and cleaned metadata must already exist in your
  S3 bucket (run `make run-pipeline` and `make run-train` locally first).
- An AWS IAM user with read access to that bucket (access key + secret).

---

## 1. Backend on Render

The repo includes a [`Dockerfile`](./Dockerfile) and a [`render.yaml`](./render.yaml)
blueprint.

1. Push this branch to GitHub.
2. In Render, click **New > Blueprint** and point it at this repo. Render reads
   `render.yaml` and creates a Docker web service named `manga-recs-api`.
   - Alternatively: **New > Web Service**, pick the repo, and choose the
     **Docker** runtime (Render auto-detects the `Dockerfile`).
3. Set these environment variables (marked `sync: false`, so they are never
   committed):

   | Variable | Description |
   | --- | --- |
   | `AWS_ACCESS_KEY_ID` | IAM access key with S3 read access |
   | `AWS_SECRET_ACCESS_KEY` | IAM secret key |
   | `AWS_DEFAULT_REGION` | Bucket region, e.g. `us-east-1` |
   | `MANGA_RECS_S3_BUCKET` | S3 bucket name (defaults to `manga-recs`) |
   | `MANGA_RECS_CORS_ORIGINS` | Your Vercel URL, e.g. `https://manga-recs.vercel.app` |

4. Deploy. Render builds the image and binds the app to its injected `$PORT`.
5. Verify health: `https://<your-service>.onrender.com/health` → `{"status":"ok"}`.

> Note: Render's free web services spin down when idle, so the first request
> after a while can be slow (cold start + S3 artifact download). The app warms
> the artifact cache on startup and loads lazily, so it won't crash if S3 is
> briefly unavailable.

---

## 2. Frontend on Vercel

1. In Vercel, **Add New > Project** and import this repo.
2. Set the **Root Directory** to `frontend` (important — the Next.js app is not
   at the repo root). Vercel auto-detects Next.js for build/output settings.
3. Add an environment variable:

   | Variable | Value |
   | --- | --- |
   | `BACKEND_URL` | Your Render URL, e.g. `https://manga-recs-api.onrender.com` |

4. Deploy. Your app will be live at `https://<project>.vercel.app`.
5. Go back to Render and set `MANGA_RECS_CORS_ORIGINS` to that Vercel URL (only
   needed if you ever call the backend directly from the browser; the proxy
   route works without it).

---

## Local end-to-end check

```bash
# Backend
make run-api            # serves on http://127.0.0.1:8000

# Frontend (separate terminal)
cd frontend
echo "BACKEND_URL=http://localhost:8000" > .env.local
npm install
npm run dev             # http://localhost:3000
```

## Refreshing the model in production

The backend reads the latest artifacts from S3. To ship new recommendations:

1. Run the pipeline + training locally (`make run-pipeline && make run-train`),
   which uploads new versioned artifacts to S3.
2. Restart the Render service (or wait for the next cold start) so it picks up
   the new files. The in-process cache lasts for the life of the process.
