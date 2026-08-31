# Active agent state

Status: idle
Owner: Claude
Branch: main
Base SHA: 95d9063 (PR #85 merged)
Scope: Consolidated handoff reconciling two parallel tracks that landed
close together: my own end-to-end gap/bug sweep (PRs #82-#84) and
Codex's A3 diagnosis (PR #85, reviewed and merged by me). Superseded the
prior STATE.md content directly rather than clobbering it silently.

## Codex's A3 diagnosis (PR #85) — reviewed and merged by Claude

Diagnosed the two historical Square/Toast menu sources (read-only
production queries, no mutation) and fixed 3 real false-positive bugs:
zero-signal JSON becoming fake menu hydration, and two independent
overly-broad "contains the word cloudflare" checks blocking benign pages
(one had a feature-flag literally named
`ecom-checkout-cloudflare-challenge-recovery`).

Independent verification I ran myself before merging (not just trusting
the PR description): reran the focused 32-test suite (matched exactly),
reran the full suite (919 passed, 2 skipped -- Codex reported 918/3, a
benign environment-dependent skip-count variance already seen elsewhere
this session, not a real discrepancy), read the new recursive payload
scorer for a DoS risk (concluded safe -- bounded by the pre-existing 5MB
payload cap, not exponential), confirmed both files lowercase text
before matching the new markers, confirmed the PR touched exactly its 7
declared files.

Conclusion (Codex's own, and confirmed by me): both sources have zero
PlaceClaim/PlaceTruth/MenuItem rows -- their historical `last_success_at`
predates PR #68's corrected success semantics, there's no orphan state
to repair. After the fixes, Itani/Toast still returns 0 valid items;
Reem's/Square returns 1 event-ticket product, correctly rejected by the
existing 2-item gate. Neither source is publishable yet -- this diagnosis
fixed real bugs but did not and could not manufacture a menu for either.

Known gap Codex flagged: local Toast Playwright escalation couldn't run
(no Chromium binary locally) -- not evidence a deployed browser worker
would or wouldn't recover a menu, just a local verification limitation.

## My own end-to-end sweep (PRs #82-#84)

- Dead code (PR #82): 2 category-query files with zero importers
  anywhere (confirmed via repo-wide grep), an abandoned parallel
  implementation from the same commit that added the real, used files.
- IDOR fix (PR #83): GET /upload/status/{image_id} required auth but
  never checked ownership -- fixed to match GET /videos/{video_id}'s
  existing pattern exactly. Found via a background research pass that
  also confirmed every other write/delete route in the app already
  scopes correctly to the authenticated user.
- N+1 fix (PR #84): menu_worker.py called recompute_places_v4 once per
  materialized place instead of once per batch, defeating that
  function's own explicit batch-fetch design. Now batches once per
  worker batch.

Also audited this pass, confirmed NOT bugs (don't re-investigate):
olo_extractor.py's "NOT IMPLEMENTED" (genuine, no public API), rate_limit.py's
IP-vs-user keying (already documented, already tracked), repo-wide sweep
for bare excepts/SQL-injection-shaped strings/frontend timer leaks (all
clean). Also E5/E6 fixed (PRs #79/#80), E7/E4 audited with no gap found
-- see prior handoff for full detail if needed.

## Current state of the Master Plan

Partial / needs production access (unchanged, still the real blockers):
- A1 (13,148-place backlog run): safe to run now -- throughput bounded
  (PR #74), N+1 fixed (PR #84). Needs your production access to execute.
- A3: diagnosis complete (above). Both sources remain correctly
  unpublished pending a bounded, verified retry -- do not retry until
  PR #85 is confirmed deployed (see Codex's own gate on this).
- A7 (source discovery), B1 steps 2/4 (real image fetch + hand-labeling).

Locked files: none currently held.
Verification plan: full backend suite green on every change (920 passed,
2 skipped as of this consolidated pass); every new/changed test
independently verified to catch its corresponding regression before
merge -- same discipline both of us have used all session.
Next action: Codex, when back: (1) confirm PR #85's deployed revision
before any retry of the two A3 sources, (2) A1 backlog run, (3) B1 steps
2/4. Claude has nothing else pending -- both open work-streams (sweep +
A3) are now merged and reconciled into this single handoff.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
