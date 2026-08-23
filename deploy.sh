#!/usr/bin/env bash
# Deploys the backend to Railway and makes the deployed commit
# independently verifiable afterward — no more guessing whether a fix
# actually shipped.
#
# `railway up` uploads this local directory as a build artifact; it does
# NOT go through a GitHub-connected clone. Confirmed live: that means
# Railway never sets RAILWAY_GIT_COMMIT_SHA, and the built container has
# no .git directory either — both of debug.py's other fallbacks come up
# empty. Stamping the current commit into backend/GIT_COMMIT.txt right
# before the upload is what actually makes it read back correctly from
# GET /api/v1/debug/version.
#
# Usage: ./deploy.sh

set -euo pipefail
cd "$(dirname "$0")"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Warning: you have uncommitted changes. GIT_COMMIT.txt will still" >&2
  echo "reflect HEAD, not your working tree — commit first if you want" >&2
  echo "the deployed commit to match what's actually running." >&2
fi

git rev-parse HEAD > backend/GIT_COMMIT.txt
echo "Stamped backend/GIT_COMMIT.txt: $(cat backend/GIT_COMMIT.txt)"

railway up

echo ""
echo "Deploy submitted. Verify it actually shipped with:"
echo "  curl https://crave-production.up.railway.app/api/v1/debug/version"
echo "Its \"commit\" field should equal: $(git rev-parse HEAD)"
