# Manga Recs

An end-to-end content-based recommender that suggests similar manga from
AniList data — data pipeline, model training, offline evaluation, HTTP API, and
web frontend, all running on free-tier infrastructure.

<!-- Fill these in after deploying (see DEPLOYMENT.md) -->
**Live demo:** _pending deploy_ · **API:** _pending deploy_

```
                    ┌─────────────────────────────────────────┐
   AniList GraphQL  │  ingest → clean → features → train      │  GitHub Actions
        API ───────►│         (quality gates between)         │◄── weekly cron
                    └──────────────────┬──────────────────────┘
                                       │  dated partitions
                                       ▼
                        S3-compatible object store
                        raw/ cleaned/ features/ models/ metrics/
                                       │
                                       ▼
   Browser ──► Vercel (Next.js) ──► Render (FastAPI) ──► loads model on boot
```

## Results

The recommender only ever sees item metadata — genres, tags, popularity, length,
release year. User read lists are never used as training signal, which makes
them a fair held-out benchmark: *do the items this model calls similar actually
get read by the same people?*

For each user with at least 5 in-catalog titles, 20% are held out. Every
candidate item is scored by its highest similarity to the user's remaining
titles, and the top 10 are compared against the held-out set. A popularity
ranker and a random ranker run through the identical harness.

| Strategy | Recall@10 | Precision@10 | NDCG@10 | Catalog coverage |
| --- | --- | --- | --- | --- |
| **Content (this model)** | **0.107** | **0.052** | **0.101** | 0.281 |
| Popularity baseline | 0.062 | 0.037 | 0.047 | 0.025 |
| Random baseline | 0.011 | 0.007 | 0.012 | 0.841 |

*963 items, 26,565 interactions from 272 users, 189 users evaluated.*

The content model recovers **74% more held-out titles than ranking by
popularity** and 9.7× more than random. The coverage column is the more
interesting one: popularity recommends from just 2.5% of the catalogue —
the same handful of famous titles to everyone — while the content model draws
on 28%, which is the entire point of a recommender.

Qualitatively, `shingeki no kyojin` returns Tokyo Ghoul, Fire Punch, and Land of
the Lustrous; `oyasumi punpun` returns The Flowers of Evil, Homunculus, and
Blood on the Tracks.

Reproduce with `make run-evaluate`.

Serving latency is ~2.5 ms p50 / 2.8 ms p95 locally, since the similarity matrix
is precomputed and held in memory.

## What's interesting here

**Storage is provider-agnostic, and that was a deliberate fix.** The first
version hardcoded `boto3.client("s3", ...)` against AWS. When the AWS account
lapsed, the whole project was dead — no data, no model, no API. It now targets
the S3 *API* rather than AWS specifically, so the same code path runs against
Cloudflare R2 in production, MinIO in local development, and AWS S3 if needed.
Switching providers is one environment variable. The practical payoff is that
`docker compose up minio` gives you the full stack with no cloud account, and
CI exercises the real `boto3` code path instead of a mock.

**Partitions are pinned per run, not resolved per stage.** Artifacts live at
`{stage}/{YYYY-MM-DD}/{file}`. Readers default to the newest partition, but a
pipeline run pins one date and threads it through every stage, so cleaning
reads exactly what that run ingested rather than whatever happens to be newest.
Re-running a date overwrites that partition and nothing else, which makes runs
idempotent and backfills safe.

**Failures are loud.** The original storage helpers caught exceptions, printed
them, and carried on — so a failed upload produced a silently stale model, and
a failed download returned a path to a file that did not exist. Every operation
now raises with the bucket and key in the message. Downloads land on a temp
name and are renamed on success, so an interrupted transfer cannot leave a
truncated file that later looks like a valid cache hit.

**The local cache is validated, not just scoped.** It used to be keyed on
filename alone, so a fresh ingest was silently served from the previous run's
download. Keying it by partition fixed the obvious case but not re-running the
same date, which overwrites an object in place — so a cache hit is now confirmed
against the remote object's size and last-modified time before it is trusted.

**Quality gates sit between stages.** Row counts, required columns, null keys,
and duplicate ids are asserted where the data is produced, so a bad frame fails
at the stage that created it instead of surfacing as a confusing error during
training. Transforms stay pure and total; enforcing invariants is the gate's job.

**Ingestion is bounded in three ways it previously was not.** A single AniList
read list could consume up to 200 paginated requests, so one power user's
library could dominate an entire run; that is now capped at 10 pages. Failing
users were retried eight times with exponential backoff, spending roughly four
minutes each to rediscover that a deleted account is still deleted; the budget
is now three attempts, and the same users skip in about thirty seconds. Most
importantly, the retry loop only handled HTTP status codes and GraphQL errors,
so a single transient read timeout killed the whole run — it now retries
transport failures too. Together these took a run that was unbounded (and had
already exceeded an hour) down to a predictable ~32 minutes.

**One inference engine, two entry points.** The HTTP API and the CLI previously
had separate copies of the recommendation logic that had already drifted — one
did fuzzy title matching, the other exact; one excluded the query from its own
results, the other did not. They now share a single `Recommender`.

**Title search covers every name a manga goes by.** Cleaning used to keep only
the English title, so searching `oyasumi punpun` or `shingeki no kyojin` — the
names many readers actually use — returned nothing. All three AniList variants
(English, romaji, native) are now indexed and resolve to the same item.

**The fuzzy scorer was chosen by measurement, not vibes.** Widening the index to
~2,500 title variants broke `rapidfuzz`'s `WRatio`, which scores partial
substring hits generously: `a` matched *Naruto* at 90, and `zzzz qqqq
nonexistent` matched *Existence* at 74, so junk queries returned confident
results instead of a 404. Scoring a labelled set of genuine and junk queries
against five scorers showed `WRatio` and `token_set_ratio` were not separable at
any threshold, while `token_sort_ratio` put every genuine query at 69 or above
and every junk query at 60 or below. Hence `token_sort_ratio` with the threshold
at 65, and regression tests pinning the junk cases.

## Quick start

Requires Python 3.10+ and Docker.

```bash
make venv && source .venv/bin/activate
make install-dev

cp .env.example .env      # defaults point at local MinIO
make minio                # start S3-compatible storage

make run-pipeline         # AniList -> raw -> cleaned -> features  (~32 min)
make run-train            # similarity matrix
make run-evaluate         # recall@k against baselines

make run-api              # http://127.0.0.1:8000/docs
```

Frontend:

```bash
cd frontend
echo "BACKEND_URL=http://localhost:8000" > .env.local
npm install && npm run dev    # http://localhost:3000
```

Ask for a recommendation without the UI:

```bash
manga-recs recommend "berserk" --top-n 5
manga-recs status               # which backend, which partitions exist
```

## Orchestration

The pipeline is a DAG of independently retryable stages, so a failure does not
force a re-run of the expensive AniList ingestion.

- **Production:** [`.github/workflows/refresh.yml`](.github/workflows/refresh.yml)
  runs weekly, writes a new partition, and fails the run if the content model
  does not beat the popularity baseline.
- **Local:** `make airflow` brings up Airflow against the same code
  ([`airflow/dags/manga_recs_dag.py`](airflow/dags/manga_recs_dag.py)) for
  developing and debugging the DAG on a real scheduler.

## Testing

```bash
make test        # everything, including MinIO integration tests
make test-unit   # no infrastructure required
make lint
```

106 tests covering the transforms, quality gates, GraphQL retry behaviour,
evaluation harness, recommender, HTTP API, and object store.

The object store tests run against real MinIO rather than a mock, because the
bugs worth catching there — endpoint resolution, addressing style, partition
ordering, cache invalidation — are exactly the ones a mock would paper over.
Likewise the GraphQL tests drive scripted timeouts and 500s through the real
retry loop, since those paths only fire when the upstream API misbehaves and
cannot be debugged interactively.

CI runs lint, the full suite against a MinIO service, and a Docker build that
must boot and answer `/health`.

## Layout

```
src/manga_recs/
  api/          FastAPI app and response schemas
  common/       settings (TOML + env), paths, constants
  data/
    extract/    AniList GraphQL clients and queries
    transform/  cleaning and feature engineering (pure functions)
    load/       S3-compatible object store client
    quality.py  inter-stage data quality gates
  models/       training and offline evaluation
  pipelines/    stage orchestration
  serving/      the shared Recommender
airflow/        local Airflow stack and the DAG
tests/          unit tests plus MinIO integration tests
configs/        base.toml, local.example.toml
```

## Configuration

`configs/base.toml` holds defaults, `configs/local.toml` overrides them per
machine, and environment variables override both. Credentials only ever come
from the environment — see [`.env.example`](.env.example).

| Variable | Purpose |
| --- | --- |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Object store credentials |
| `AWS_DEFAULT_REGION` | `auto` for R2, a real region for AWS |
| `MANGA_RECS_S3_ENDPOINT_URL` | S3-compatible endpoint; unset means AWS |
| `MANGA_RECS_S3_BUCKET` | Bucket name |
| `MANGA_RECS_CORS_ORIGINS` | Comma-separated frontend origins |

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full walkthrough: Cloudflare R2,
Render, Vercel, and the scheduled refresh.

## Limitations

- Content-based only. There is no collaborative filtering, so the model cannot
  learn that unrelated-looking titles share an audience. The user interaction
  data is already ingested and would be the natural next step.
- Cold start on Render's free tier: the first request after idle pays a
  container start plus an artifact download.
- The catalogue is filtered to reasonably popular, well-rated titles
  (`popularity > 10000`, `score > 70`), so obscure manga are not represented.
