#!/usr/bin/env bash
# Boot the demo image the way Hugging Face Spaces does - read-only root
# filesystem, only /tmp writable, non-root UID - and assert the service actually
# answers. A built image that cannot serve a request is not a passing build, and
# a read-only filesystem is the most common reason a Space dies after working
# locally.
set -euo pipefail

IMAGE="${1:-manga-recs}"
PORT="${2:-7860}"
CONTAINER="manga-recs-smoke-$$"

cleanup() {
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "==> Starting $IMAGE read-only on port $PORT"
docker run -d --name "$CONTAINER" \
    -p "${PORT}:7860" \
    --read-only --tmpfs /tmp \
    "$IMAGE" >/dev/null

echo "==> Waiting for /health"
for attempt in $(seq 1 45); do
    if curl -sf "http://localhost:${PORT}/health" >/tmp/health.json 2>/dev/null; then
        break
    fi
    if [ "$attempt" -eq 45 ]; then
        echo "FAIL: service never became reachable"
        docker logs "$CONTAINER"
        exit 1
    fi
    sleep 2
done

echo "--- GET /health"
cat /tmp/health.json
echo

# A degraded health response means the artifacts are missing, which for the
# baked-in bundle means the image was built wrong.
if ! grep -q '"model_loaded":true' /tmp/health.json; then
    echo "FAIL: model did not load; the bundle is missing from the image"
    docker logs "$CONTAINER"
    exit 1
fi

echo "--- POST /recommendations/ (Berserk)"
curl -sf -X POST "http://localhost:${PORT}/recommendations/" \
    -H 'Content-Type: application/json' \
    -d '{"title":"Berserk","top_n":3}' >/tmp/recs.json
cat /tmp/recs.json
echo

python3 - <<'PY'
import json
import sys

with open("/tmp/recs.json") as handle:
    payload = json.load(handle)

recs = payload.get("recommendations", [])
if len(recs) != 3:
    sys.exit(f"FAIL: expected 3 recommendations, got {len(recs)}")
if not all(r.get("title") for r in recs):
    sys.exit("FAIL: a recommendation came back without a title")
# Ranking must be monotonic; an unsorted response means the join regressed.
scores = [r["similarity"] for r in recs]
if scores != sorted(scores, reverse=True):
    sys.exit(f"FAIL: recommendations are not sorted by similarity: {scores}")
print(f"OK: 3 ranked recommendations, top similarity {scores[0]}")
PY

echo "--- GET / (UI)"
curl -sf "http://localhost:${PORT}/" -o /tmp/ui.html
grep -q "Manga Recommendations" /tmp/ui.html \
    && echo "OK: UI served from the same origin as the API"

echo "--- Unknown title returns 404"
status=$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://localhost:${PORT}/recommendations/" \
    -H 'Content-Type: application/json' \
    -d '{"title":"zzzz qqqq nonexistent"}')
[ "$status" = "404" ] && echo "OK: 404 for an unmatchable title" || {
    echo "FAIL: expected 404, got $status"
    exit 1
}

echo
echo "==> Smoke test passed"
