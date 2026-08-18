#!/usr/bin/env bash
#
# Publish the current commit to a Hugging Face Space.
#
# A Docker Space requires YAML frontmatter at the top of README.md, which has no
# business in the project's GitHub README. Rather than maintain two READMEs or a
# permanently diverged branch, this builds a throwaway commit in a temporary
# worktree with the Space README swapped in, pushes that, and deletes it. The
# branch you are on is never modified.
#
# Usage:
#   scripts/deploy_hf.sh <hf-username> [space-name]
#
set -euo pipefail

USERNAME="${1:?usage: scripts/deploy_hf.sh <hf-username> [space-name]}"
SPACE="${2:-manga-recs}"
REMOTE="https://huggingface.co/spaces/${USERNAME}/${SPACE}"

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

if [ -n "$(git status --porcelain)" ]; then
  echo "error: working tree is dirty. Commit or stash first so the Space matches a real commit." >&2
  exit 1
fi

if [ ! -f artifacts/serving/cosine_sim.pkl ]; then
  echo "error: artifacts/serving is empty. Run 'make bundle' first." >&2
  exit 1
fi

WORKTREE="$(mktemp -d)"
cleanup() {
  git worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true
  rm -rf "$WORKTREE"
}
trap cleanup EXIT

echo "==> Staging a deploy tree from $(git rev-parse --short HEAD)"
git worktree add --detach --quiet "$WORKTREE" HEAD
cp deploy/huggingface/README.md "$WORKTREE/README.md"

cd "$WORKTREE"

# The Space only needs to build and serve. Everything else is noise in a
# public build context and slows the upload.
rm -rf airflow tests scripts data mlruns mlflow.db notebooks .github deploy

git add -A
git -c user.email="deploy@localhost" -c user.name="deploy" \
  commit --quiet -m "Deploy $(git -C "$REPO_ROOT" rev-parse --short HEAD)"

echo "==> Pushing to ${REMOTE}"
echo "    (force-push targets the Space only; it never touches origin)"
git push --force "$REMOTE" HEAD:refs/heads/main

echo
echo "Done. Build logs: ${REMOTE}?logs=build"
echo "Live once green:  https://${USERNAME}-${SPACE}.hf.space"
