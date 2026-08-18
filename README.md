# Manga Recs

An end-to-end content-based recommender that suggests similar manga from
AniList data — data pipeline, model training, offline evaluation, HTTP API, and
web frontend, all running on free-tier infrastructure.

<!-- Fill in after deploying: see DEPLOYMENT.md -->
**Live demo:** _pending deploy_

## Architecture

Training and serving are separated on purpose, and only one of them needs
credentials.

```
  TRAINING — credentialed, scheduled, offline
                    ┌─────────────────────────────────────────┐
   AniList GraphQL  │  ingest → clean → features → train      │  GitHub Actions
        API ───────►│         (quality gates between)         │◄── weekly cron
                    └──────────────────┬──────────────────────┘
                                       │  dated partitions
                                       ▼
                        S3-compatible object store
                        raw/ cleaned/ features/ models/ metrics/
                                       │
                                       │  make bundle  (explicit promotion)
                                       ▼
  SERVING — no credentials, no network
                    ┌─────────────────────────────────────────┐
   Browser ────────►│  one container                          │
                    │    FastAPI ─ /recommendations/ /health  │
                    │            ─ /metrics                   │
                    │            └ static UI (Next.js export) │
                    │  baked in: cosine_sim.pkl        7.5 MB │
                    │            manga_metadata.parquet 0.5 MB│
                    └─────────────────────────────────────────┘
```

The serving path needs 7.9 MB of artifacts, so they are committed and copied
into the image at build time. Nothing is fetched to answer a request: no bucket,
no keys, no egress, and no failure mode where the demo is down because storage
is unreachable. One container serves the API and the UI on one origin, which
also removes CORS and the proxy route the split deployment needed.

The object store has not gone away — it is how the pipeline publishes dated
partitions — it is just no longer in the request path. Promotion is therefore
explicit: `make bundle`, commit, redeploy. A bad training run cannot silently
become the live model.

## Results

The recommender only ever sees item metadata — genres, tags, authors, popularity,
length, release year. User read lists are never used as training signal, which
makes them a fair held-out benchmark: *do the items this model calls similar
actually get read by the same people?*

For each user with at least 5 in-catalog titles, 20% are held out. Every
candidate item is scored by its highest similarity to the user's remaining
titles, and the top 10 are compared against the held-out set. A popularity
ranker and a random ranker run through the identical harness.

| Strategy | Recall@10 | Precision@10 | NDCG@10 | Catalog coverage |
| --- | --- | --- | --- | --- |
| **Content (this model)** | **0.109** | **0.055** | **0.114** | 0.276 |
| Popularity baseline | 0.062 | 0.034 | 0.045 | 0.023 |
| Random baseline | 0.006 | 0.004 | 0.006 | 0.856 |

*965 items, 26,569 interactions from 272 users, 186 users evaluated.*

The content model recovers **76% more held-out titles than ranking by
popularity**, and its NDCG is 2.5× higher, meaning the titles it does recover
sit nearer the top. Coverage is the more interesting column: popularity
recommends from 2.3% of the catalogue — the same handful of famous titles to
everyone — while the content model draws on 28%, which is the entire point of a
recommender.

> These numbers are not comparable to any published earlier in the project's
> history. The relevance definition was wrong until recently: AniList returns
> each user's score in that user's own scale, so one column mixed 0-3, 0-5,
> 0-10 and 0-100 across 272 users, and the positive threshold compared it
> against `7.0`. That admitted anything rated at all, including 104 titles
> users had explicitly dropped. Scores are now requested as POINT_100 and
> relevance is a graded interaction strength. The positive set got smaller and
> better founded, so absolute numbers moved; the comparison against the
> baselines, which run through the identical harness, is the part that means
> anything.

Qualitatively, `uzumaki` returns Tomie and The Enigma of Amigara Fault — both
Junji Ito — alongside Tokyo Ghoul; `oyasumi punpun` returns The Flowers of Evil,
Homunculus, and Blood on the Tracks.

Reproduce with `make run-evaluate`.

### Do author features actually help?

Adding authors improves every metric, but that alone proves nothing: adding any
sparse high-cardinality column inflates the norms of the rows it touches, which
demotes obscure titles and flatters top-K metrics. So each arm is re-run with
the author-to-title mapping randomly permuted — identical columns and sparsity,
no signal — and compared pairwise per user with a bootstrapped interval.

| Arm | Features | Recall@10 | NDCG@10 | vs shuffled twin |
| --- | --- | --- | --- | --- |
| No authors | 388 | 0.1006 | 0.0952 | — |
| **Authors, ≥1 credit** | 1629 | **0.1094** | **0.1141** | +0.0086, CI [+0.0002, +0.0182] |
| Authors, ≥2 credits | 566 | 0.0989 | 0.1060 | −0.0027, CI spans zero |

Only the unfiltered arm separates from its control, and it barely does. The
reach analysis explains why: just 404 of 470,935 title pairs share an author, so
the feature can influence 0.086% of the matrix and could not move an aggregate
metric even with a perfect signal.

recall@10 was simply the wrong instrument. Measured directly, author features
raise same-author titles surfaced in the top 10 from 218 to 278 across the 353
titles with a same-author sibling — a 28% lift on the question the feature
exists to answer, and visible in the Uzumaki example above.

Reproduce with `python scripts/author_ablation.py`.

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
