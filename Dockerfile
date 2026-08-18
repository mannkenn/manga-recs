# Single-container demo: FastAPI serves both the JSON API and the built UI, with
# model artifacts baked in. Nothing is fetched at runtime, so the image needs no
# credentials, no bucket, and no network access to answer a request.
#
# Targets Hugging Face Spaces (Docker SDK), which means: listen on 7860, run as
# UID 1000, and tolerate a read-only root filesystem with only /tmp writable.

# ---- Stage 1: build the static frontend ----------------------------------
FROM node:20-slim AS frontend

# Both build stages install from public registries. On a network that terminates
# TLS, the interception CA is not in these base images, so allow the operator to
# relax verification at build time. Defaults are the secure values; Spaces and CI
# never need to override them.
ARG NPM_CONFIG_STRICT_SSL=true

WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# next.config.js sets output: 'export', so this emits a fully static ./out.
RUN npm run build


# ---- Stage 2: runtime ----------------------------------------------------
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Anything that insists on a home or temp directory must land in the one
    # writable mount, because the rest of the filesystem is read-only on Spaces.
    HOME=/tmp \
    XDG_CACHE_HOME=/tmp/.cache \
    MPLCONFIGDIR=/tmp/.cache/matplotlib \
    # Serve strictly from the baked-in bundle: never reach for an object store.
    MANGA_RECS_ARTIFACT_SOURCE=bundle \
    MANGA_RECS_STATIC_DIR=/app/static \
    PORT=7860

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Dependency metadata first so the install layer caches across source changes.
# See NPM_CONFIG_STRICT_SSL above. pip reads PIP_* variables from the
# environment, and ARG values are visible to RUN, so passing
# --build-arg PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org" is enough.
ARG PIP_TRUSTED_HOST=""

COPY pyproject.toml ./
COPY src ./src
RUN pip install --upgrade pip && pip install .

COPY configs ./configs
COPY artifacts/serving ./artifacts/serving
COPY --from=frontend /ui/out ./static

# Spaces runs containers as UID 1000. Create that user explicitly and make the
# baked artifacts readable by it, rather than relying on root at runtime.
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app \
    && chmod -R a+rX /app/artifacts /app/static
USER 1000

EXPOSE 7860

# Hits the app's own port so the check follows PORT rather than assuming 7860.
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT:-7860}/health" || exit 1

CMD ["sh", "-c", "uvicorn manga_recs.api.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
