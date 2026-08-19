# Deployment

Two things deploy independently, and they are deliberately decoupled:

```
  SERVING  (no credentials, no network)
  ┌──────────────────────────────────────────────┐
  │  Hugging Face Space — one Docker container   │
  │                                              │
  │   FastAPI ── /health  /recommendations/      │
  │           ── /metrics                        │
  │           └─ static UI (Next.js export)      │
  │                                              │
  │   baked in: cosine_sim.pkl         7.1 MB    │
  │             manga_metadata.json.gz 0.4 MB    │
  └──────────────────────────────────────────────┘

  PIPELINE  (credentialed, runs elsewhere)
  ┌──────────────────────────────────────────────┐
  │  GitHub Actions, weekly                      │
  │   AniList ─> raw ─> cleaned ─> features      │
  │           ─> train ─> evaluate               │
  │                    ↓                         │
  │        S3-compatible object store (R2)       │
  └──────────────────────────────────────────────┘
```

The running demo reads nothing at runtime. Both artifacts it needs come to
7.9 MB, so they are committed under `artifacts/serving/` and copied into the
image at build time. That removes every credential from the serving path: no
bucket, no keys, no egress, and no failure mode where the demo is down because
storage is unreachable.

The object store still matters — it is how the pipeline publishes dated
partitions, and how a refreshed model gets from a scheduled run to a new
bundle — but it is not in the request path.

Promoting a new model is therefore explicit: `make bundle` pulls the latest
published partition into `artifacts/serving/`, you commit it, and redeploy. A
bad training run cannot silently become the live model.

---

## Deploy to Hugging Face Spaces

Prerequisites: an account on <https://huggingface.co/join>, and `git` with the
credential helper able to store a token.

### 1. Create a write token

<https://huggingface.co/settings/tokens> → **New token** → type **Write**. Copy it.

### 2. Create the Space

<https://huggingface.co/new-space>

| Field | Value |
| --- | --- |
| Owner | your username |
| Space name | `manga-recs` |
| License | MIT |
| SDK | **Docker** → **Blank** |
| Hardware | CPU basic (free) |
| Visibility | Public |

Leave everything else alone. `app_port` comes from the README frontmatter that
the deploy script pushes, so there is nothing to configure in the UI.

### 3. Push

```bash
make bundle                        # only if artifacts/serving is stale
scripts/deploy_hf.sh <your-hf-username>
```

Git will prompt for credentials: username is your HF username, password is the
**write token** from step 1.

> The Hugging Face account here is `emmanuelkim`, which is **not** the GitHub
> account (`mannkenn`) — so this deploy is `scripts/deploy_hf.sh emmanuelkim`,
> publishing to <https://emmanuelkim-manga-recs.hf.space/>. That URL is linked
> externally, so keep the Space name as `manga-recs`: renaming it changes the
> hostname and breaks the link.

The script builds the Space commit in a throwaway worktree — it swaps in
`deploy/huggingface/README.md`, which carries the mandatory YAML frontmatter,
and drops tests, CI config and local data. Your branch is untouched, and the
project README never grows a `sdk: docker` header.

### 4. Watch it build

```
https://huggingface.co/spaces/<username>/manga-recs?logs=build
```

First build takes 3-5 minutes, most of it `npm ci` and the wheel installs. When
it goes green:

```bash
curl https://<username>-manga-recs.hf.space/health
```

```json
{"status":"ok","model_loaded":true,"items":965,
 "artifact_source":"bundle","model_partition":"2026-08-18"}
```

`"artifact_source":"bundle"` is the thing to check. It confirms the container
answered from baked-in artifacts rather than reaching for a bucket it has no
credentials for.

### 5. Recommended Space settings

Under **Settings → Variables and secrets**, add one variable (not a secret):

| Name | Value | Why |
| --- | --- | --- |
| `MANGA_RECS_TRUST_FORWARDED_FOR` | `true` | Spaces proxies the container, so without this every visitor shares one apparent IP and the rate limiter throttles them as a single client. |

No secrets are needed. If you find yourself adding an access key, something has
regressed — check `MANGA_RECS_ARTIFACT_SOURCE` is still `bundle`.

---

## Verifying locally before you push

The Space constraints that actually break builds are the read-only filesystem
and the non-root user. Reproduce both:

```bash
make docker-build
docker run --rm -p 7860:7860 --read-only --tmpfs /tmp --user 1000:1000 manga-recs
```

```bash
curl -s localhost:7860/health
curl -s -X POST localhost:7860/recommendations/ \
  -H 'Content-Type: application/json' \
  -d '{"title":"Berserk","topN":3}'
```

Or in one step, which also checks the UI, the 404 path and the metrics
endpoint:

```bash
make docker-smoke
```

If the container starts as root locally but not on Spaces, you are missing
`--user 1000:1000`. If it works read-write and dies read-only, something is
writing into `/app`; `HOME`, `XDG_CACHE_HOME` and `MPLCONFIGDIR` are already
pointed at `/tmp` in the Dockerfile, so the culprit is usually new code writing
a relative path.

---

## The pipeline

Only needed to produce a *new* model. The committed bundle is enough to serve.

### Object storage

Any S3-compatible store. The endpoint is a config value, so the provider is a
choice rather than a dependency:

| Provider | Endpoint | Free tier | Expires |
| --- | --- | --- | --- |
| Cloudflare R2 | `https://<account>.r2.cloudflarestorage.com` | 10 GB, zero egress | Never |
| AWS S3 | *(unset)* | 5 GB | Free plan closes the account after 6 months |
| MinIO | `http://localhost:9000` | Local only | n/a |

R2 is the default recommendation: permanent free tier and no egress charges.
AWS is avoided because since July 2025 a new account on the Free plan is closed
after six months, taking its contents with it — a poor fit for something you
want reachable while job hunting.

```bash
cp .env.example .env
```

```env
AWS_ACCESS_KEY_ID=<access-key-id>
AWS_SECRET_ACCESS_KEY=<secret-access-key>
AWS_DEFAULT_REGION=auto
MANGA_RECS_S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
MANGA_RECS_S3_BUCKET=manga-recs
```

```bash
make status          # confirm connectivity before anything expensive
```

### Run it

```bash
make install-dev
make run-pipeline    # AniList -> raw -> cleaned -> features
make run-train       # similarity matrix
make run-evaluate    # recall@10 / precision@10 / NDCG@10 vs baselines
make bundle          # pull the new partition into artifacts/serving/
```

`make run-pipeline` takes roughly 40 minutes, nearly all of it waiting on
AniList's rate limit. That is deliberate: the limiter is set to 30 req/min
because AniList frequently serves a degraded quota, and cranking it earns 429s
rather than speed.

Review the evaluation output before committing a new bundle. If the metrics
regressed, the old bundle is still in git and still serving.

### Scheduled refresh

[`.github/workflows/refresh.yml`](./.github/workflows/refresh.yml) re-runs the
pipeline weekly and publishes a new dated partition. Add under **Settings →
Secrets and variables → Actions**:

- `AWS_ACCESS_KEY_ID` (read-write token)
- `AWS_SECRET_ACCESS_KEY`
- `AWS_DEFAULT_REGION` → `auto`
- `MANGA_RECS_S3_ENDPOINT_URL`
- `MANGA_RECS_S3_BUCKET`

It publishes artifacts; it does not touch the Space. Promotion stays manual.

---

## Local development

```bash
make minio                                   # local S3-compatible storage
make run-pipeline && make run-train          # populate it
make run-api                                 # http://127.0.0.1:8000

cd frontend
echo "NEXT_PUBLIC_API_BASE=http://localhost:8000" > .env.local
npm install && npm run dev                   # http://localhost:3000
```

In the deployed image FastAPI serves the built frontend, so the two share an
origin and there is no CORS. `next dev` runs on a separate port, which is what
`NEXT_PUBLIC_API_BASE` is for.

To exercise the DAG the way a scheduler would:

```bash
make airflow                                 # http://localhost:8080 (airflow/airflow)
```

---

## Observability

The service emits structured JSON logs, OpenTelemetry spans, and Prometheus
metrics. All three work with nothing configured — spans go to a no-op exporter
by default, so no collector is needed and the demo cannot break for want of one.

| Variable | Default | Effect |
| --- | --- | --- |
| `MANGA_RECS_LOG_JSON` | `true` | `false` gives human-readable logs locally |
| `LOG_LEVEL` | `INFO` | |
| `MANGA_RECS_TRACE_EXPORTER` | *(none)* | `console`, or `otlp` to export |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | Collector URL when exporter is `otlp` |

Pointing at a real backend is a config change, not a code change:

```bash
docker run --rm -p 7860:7860 \
  -e MANGA_RECS_TRACE_EXPORTER=otlp \
  -e OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4317 \
  manga-recs
```

Requires the OTLP extra: `pip install -e ".[otlp]"`.

What to look at when it misbehaves:

| Symptom | Signal |
| --- | --- |
| Demo returns 503 | `manga_recs_model_loaded` is 0; `/health` carries the reason in `detail` |
| Serving a stale model | `manga_recs_model_info{partition=...}` |
| "It found nothing for my search" | `manga_recs_title_not_found_total` rising, and `manga_recs_title_match_score` shifting toward the low buckets |
| Slow responses | `manga_recs_request_duration_seconds` vs `manga_recs_recommendation_duration_seconds` — if only the former moved, the time is in HTTP or startup, not the model |
| Someone hammering it | `manga_recs_rate_limited_total`, labelled by route |

Every log line carries `request_id`, plus `trace_id` and `span_id` when tracing
is enabled, so a line found by text search joins to its trace. The id is echoed
in the `X-Request-ID` response header, which means a user reporting a slow
request can quote something findable.

---

## Troubleshooting

**Space build fails at `npm ci`**
The lockfile and `package.json` disagree. Run `npm install` in `frontend/` and
commit the updated `package-lock.json`.

**Space builds but shows "Application starting" forever**
The container is not listening on 7860. Check `app_port: 7860` survived in the
pushed README — `head -10 README.md` inside the Space repo.

**The `.hf.space` URL returns a Hugging Face 404 page**
Not the application's 404 — check for the `X-Response-Time-ms` header, which
this service sets on every response and Hugging Face's own error page does not.
Its absence means the request never reached the container: the Space does not
exist under that exact owner and name, is still on its first build, or is set to
**Private**, which 404s for anonymous visitors. Anything linked externally has
to be Public.

**`/health` reports `degraded` with `artifact_source` absent**
The bundle is missing from the image. Confirm `artifacts/serving/` is committed
(`git ls-files artifacts/serving`) and that `.dockerignore` still allows it.

**Works locally, dies on Spaces**
Almost always the read-only filesystem. Reproduce with
`docker run --read-only --tmpfs /tmp --user 1000:1000`.

**`No partitions found under s3://manga-recs/models/`**
Pipeline-only. The bucket is empty; run `make run-pipeline && make run-train`.

**`SSLCertVerificationError` when running the pipeline**
Your network intercepts TLS. Point Python at a trust store that includes the
interception CA:

```bash
python -c "import certifi;print(certifi.where())" | xargs cat > /tmp/ca.pem
security find-certificate -a -p /Library/Keychains/System.keychain >> /tmp/ca.pem
export REQUESTS_CA_BUNDLE=/tmp/ca.pem
```

For the Docker build on such a network:

```bash
docker build -t manga-recs \
  --build-arg NPM_CONFIG_STRICT_SSL=false \
  --build-arg PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org" .
```

Or through the Makefile, which passes the flags on to `docker build`:

```bash
make docker-smoke DOCKER_BUILD_ARGS='--build-arg NPM_CONFIG_STRICT_SSL=false \
  --build-arg PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org"'
```

Those arguments default to the secure values and are never needed on Spaces or
in CI.
