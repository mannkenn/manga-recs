FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY configs ./configs
RUN pip install --upgrade pip && pip install .

# Render (and most platforms) inject the port to bind to via $PORT.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn manga_recs.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
