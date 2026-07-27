#!/usr/bin/env bash
#
# CRAVE — run every check across backend + frontend in one go.
# Nothing here stops the script early: each step runs independently, a
# failure is recorded, and the run moves on to the next step. A summary
# prints at the end so you can see pass/fail for everything in one place.
#
# Usage: paste this whole file into a terminal at the repo root
# (/Users/angelowashington/CRAVE), or run `bash run_everything.sh`.

set +e  # do not abort on the first failing command

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS=()

run_step() {
  local name="$1"
  shift
  echo ""
  echo "=================================================="
  echo "  $name"
  echo "=================================================="
  "$@"
  local code=$?
  if [ $code -eq 0 ]; then
    RESULTS+=("PASS  $name")
  else
    RESULTS+=("FAIL  $name  (exit $code)")
  fi
}

# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------
cd "$REPO_ROOT/backend" || { echo "backend/ not found — aborting"; exit 1; }

run_step "Backend: pip install (requirements-dev.txt)" \
  pip install -r requirements-dev.txt

run_step "Backend: syntax compile check (every .py file)" \
  python -m compileall -q app

run_step "Backend: import sanity check" \
  env APP_ENV=dev python -c "import app.main; print('import OK')"

run_step "Backend: pytest suite (all 20 files under tests/)" \
  env APP_ENV=dev DATABASE_URL="sqlite:///./test_crave.db" pytest -q --tb=short

# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
cd "$REPO_ROOT/frontend" || { echo "frontend/ not found — aborting"; exit 1; }

# npm install (not `npm ci`) on purpose — package-lock.json is currently out
# of sync with package.json (see CRAVE_REMAINING_WORK.md), and this will
# regenerate/update the lockfile instead of hard-failing on the mismatch.
run_step "Frontend: npm install" \
  npm install

run_step "Frontend: TypeScript typecheck" \
  npx tsc --noEmit

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
cd "$REPO_ROOT"

echo ""
echo "=================================================="
echo "  SUMMARY"
echo "=================================================="
for r in "${RESULTS[@]}"; do
  echo "$r"
done
echo ""
echo "Full output for any FAIL line is above, under that step's own header."
