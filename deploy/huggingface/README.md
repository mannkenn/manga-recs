---
title: Manga Recommender
emoji: 📚
colorFrom: indigo
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# Manga Recommender

Content-based manga recommendations over ~965 titles from AniList, scored by
cosine similarity across genres, tags, authors, and normalised numeric metadata.

One container serves both the API and the UI. The similarity matrix and title
metadata are baked into the image, so the running Space needs no database, no
object storage, and no credentials.

- `GET /health` — readiness, item count, and which artifact source answered
- `POST /recommendations/` — `{"title": "berserk", "topN": 5}`
- `GET /metrics` — Prometheus exposition

Source and engineering notes: <https://github.com/mannkenn/manga-recs>
