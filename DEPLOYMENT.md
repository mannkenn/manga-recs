# Deployment

The system deploys as three independent pieces:

```
Browser ──> Vercel (Next.js)  ──>  Render (FastAPI)  ──>  Cloudflare R2
             /api/recommendations     /recommendations/     model + metadata

GitHub Actions (weekly cron) ──> AniList ──> Cloudflare R2
```

The frontend never calls the backend directly from the browser. It proxies
through its own server-side route (`/api/recommendations`), which keeps the
backend URL out of client bundles and sidesteps CORS entirely.

Everything below runs on free tiers with no expiry.

---

## Why not AWS?

The original build used AWS S3. As of July 2025 a new AWS account has to pick a
Free plan or a Paid plan, and **the Free plan closes your account after six
months**, deleting whatever is in it. That is a bad fit for a portfolio project
you want reachable while job hunting.

The application talks to an **S3-compatible API** rather than to AWS
specifically, so the storage provider is a config value:

| Provider | Endpoint | Free tier | Expires |
| --- | --- | --- | --- |
| Cloudflare R2 | `https://<account>.r2.cloudflarestorage.com` | 10 GB, zero egress | Never |
| AWS S3 | *(unset)* | 5 GB always-free | Never on the Paid plan |
| MinIO | `http://localhost:9000` | Local only | n/a |

R2 is the default recommendation here: permanent free tier, no egress charges,
and no card-on-file countdown. Switching to AWS later is one environment
variable.

---

## 1. Object storage (Cloudflare R2)

1. Create a free account at <https://dash.cloudflare.com/sign-up>.
2. In the sidebar choose **R2 Object Storage**. Enabling R2 asks for a card for
   overage protection, but the 10 GB free tier never expires and this project
   stores well under 100 MB.
3. **Create bucket** named `manga-recs`. Location `Automatic` is fine.
4. Go to **R2 → API → Manage API Tokens → Create API Token**.
   - Permission: **Object Read & Write**
   - Scope it to the `manga-recs` bucket only.
   - Create, then copy the **Access Key ID** and **Secret Access Key**. The
     secret is shown exactly once.
5. Note your **S3 API endpoint**, shown on the bucket settings page as
   `https://<account-id>.r2.cloudflarestorage.com`.

Put those into `.env` locally:

```bash
cp .env.example .env
```

```env
AWS_ACCESS_KEY_ID=<r2-access-key-id>
AWS_SECRET_ACCESS_KEY=<r2-secret-access-key>
AWS_DEFAULT_REGION=auto
MANGA_RECS_S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
MANGA_RECS_S3_BUCKET=manga-recs
```

Confirm the connection before doing anything expensive:

```bash
make status
```

---

## 2. Populate the bucket

The API serves precomputed artifacts, so the bucket has to be filled once
before any deploy is useful.

```bash
make install-dev
make run-pipeline    # AniList -> raw -> cleaned -> features   (~32 min)
make run-train       # similarity matrix -> models/
make run-evaluate    # recall@k vs baselines -> metrics/
```

Verify:

```bash
make status
```

You should see a partition under each of `raw`, `cleaned`, `features`,
`models`, and `metrics`.

---

## 3. Backend on Render

The repo ships a [`Dockerfile`](./Dockerfile) and a
[`render.yaml`](./render.yaml) blueprint.

1. Push the branch to GitHub.
2. In Render: **New → Blueprint**, point it at the repo. Render reads
   `render.yaml` and creates a Docker web service named `manga-recs-api`.
3. Fill in the environment variables (all marked `sync: false`, so none are
   stored in the repo):

   | Variable | Value |
   | --- | --- |
   | `AWS_ACCESS_KEY_ID` | R2 access key id |
   | `AWS_SECRET_ACCESS_KEY` | R2 secret access key |
   | `AWS_DEFAULT_REGION` | `auto` |
   | `MANGA_RECS_S3_ENDPOINT_URL` | `https://<account-id>.r2.cloudflarestorage.com` |
   | `MANGA_RECS_S3_BUCKET` | `manga-recs` |
   | `MANGA_RECS_CORS_ORIGINS` | your Vercel URL, added after step 4 |

   For the deployed API a **read-only** R2 token is sufficient and preferable —
   it never writes. Create a second token with Object Read permission and use
   that here, keeping the read-write pair for the pipeline.

4. Deploy, then check `https://<service>.onrender.com/health`:

   ```json
   {"status": "ok", "model_loaded": true, "items": 1400}
   ```

   `"model_loaded": false` means the service is running but could not read the
   bucket — check the credentials and endpoint.

> Render's free tier spins services down when idle, so the first request after
> a quiet period pays a cold start plus an artifact download. The service warms
> its cache on startup and loads lazily, so it reports `degraded` rather than
> crashing if storage is briefly unreachable.

---

## 4. Frontend on Vercel

1. **Add New → Project**, import the repo.
2. Set **Root Directory** to `frontend`. This matters — the Next.js app is not
   at the repo root. Vercel then auto-detects the framework.
3. Add an environment variable:

   | Variable | Value |
   | --- | --- |
   | `BACKEND_URL` | `https://<service>.onrender.com` |

4. Deploy. Then go back to Render and set `MANGA_RECS_CORS_ORIGINS` to your
   Vercel URL.

---

## 5. Scheduled retraining

[`.github/workflows/refresh.yml`](./.github/workflows/refresh.yml) re-runs the
pipeline, retrains, and re-evaluates every Monday at 06:00 UTC, writing a new
dated partition. Add these under **Settings → Secrets and variables → Actions**:

- `AWS_ACCESS_KEY_ID` (read-write R2 token)
- `AWS_SECRET_ACCESS_KEY`
- `AWS_DEFAULT_REGION` → `auto`
- `MANGA_RECS_S3_ENDPOINT_URL`
- `MANGA_RECS_S3_BUCKET`

Trigger a manual run from the Actions tab to confirm it works. Evaluation
metrics are published to the workflow summary and uploaded as an artifact.

The backend picks up the new partition on its next restart, since readers
resolve the latest partition at load time and cache for the process lifetime.

---

## Local end-to-end check

```bash
make minio                                   # local S3-compatible storage
make run-pipeline && make run-train          # populate it
make run-api                                 # http://127.0.0.1:8000

cd frontend
echo "BACKEND_URL=http://localhost:8000" > .env.local
npm install && npm run dev                   # http://localhost:3000
```

To exercise the DAG the way a real scheduler would:

```bash
make airflow                                 # http://localhost:8080 (airflow/airflow)
```

---

## Troubleshooting

**`No partitions found under s3://manga-recs/models/`**
The bucket is empty. Run `make run-pipeline && make run-train`.

**`no object store credentials found`**
`.env` is missing or not being read. Confirm with `make status`.

**Health check returns `degraded`**
The service is up but cannot read artifacts — usually a wrong
`MANGA_RECS_S3_ENDPOINT_URL`, or a token scoped to the wrong bucket.

**`SSLCertVerificationError` when running the pipeline**
Your machine intercepts TLS (common on corporate networks). Point Python at a
trust store that includes the interception CA:

```bash
python -c "import certifi;print(certifi.where())" | xargs cat > /tmp/ca.pem
security find-certificate -a -p /Library/Keychains/System.keychain >> /tmp/ca.pem
export REQUESTS_CA_BUNDLE=/tmp/ca.pem
```
