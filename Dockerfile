FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Dependency metadata first so the install layer caches across source changes.
COPY pyproject.toml ./
COPY src ./src
COPY configs ./configs
RUN pip install --upgrade pip && pip install .

# The service downloads model artifacts into ./data at runtime, so it needs a
# writable working directory even though it does not run as root.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app
USER appuser

ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT:-8000}/health" || exit 1

CMD ["sh", "-c", "uvicorn manga_recs.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
