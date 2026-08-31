# Active agent state

Status: idle
Owner: Claude
Branch: main
Base SHA: 2d97f11 (PR #84 merged)
Scope: End-to-end gap/bug sweep across the whole project, per the user's
"search project end to end for all gaps and bugs and anything broken if
u can fix it, if not leave and log for codex" instruction. Still working
solo since Codex's session is offline.

Done this pass (since the last STATE.md update, which covered through
PR #81):
- Dead code (PR #82): app/services/query/categories_query.py (103 lines,
  its own parallel get_categories/get_category/get_category_by_slug) and
  categories.py (0-byte empty file) had zero importers anywhere in app/
  or tests/ -- confirmed via repo-wide grep before deleting. Both look
  like an abandoned parallel implementation from the same commit
  (79c5343) that added the real, actually-used category_query.py and
  place_category_query.py.
- IDOR fix (PR #83): GET /upload/status/{image_id} required auth but
  never checked ownership -- any authenticated user could poll any other
  user's photo upload and read moderation_reason/error_message (internal
  review-queue detail). Fixed to match the exact pattern already used by
  GET /videos/{video_id} (uploaded_by != user_id -> 403). Found by a
  background research pass specifically hunting IDOR/N+1 patterns; that
  same pass checked blocks.py/follows.py/hitlist.py/rankings.py/
  saves.py/account.py/profile.py/moderation.py/menu_submissions.py and
  confirmed all correctly scope writes/deletes to the authenticated user
  already -- this was the one real gap.
- N+1 fix (PR #84): menu_worker.py called recompute_places_v4(db,
  places=[place]) once per successfully-materialized place inside its
  per-place loop, defeating that function's own explicitly batch-fetch
  design (_fetch_signal_context's own docstring: "never per-place").
  A 40-place batch materializing N menus cost N x 7 signal queries
  instead of 7 total, plus N redundant per-city cache invalidations.
  Now collects materialized places across the batch and calls it once
  after the per-place loop, still in the same session -- each place's
  own extraction result was already committed per-place earlier in the
  loop, so the batched call reads correct state regardless of ordering.

Also audited, no code change needed:
- app/services/menu/providers/olo_extractor.py's "NOT IMPLEMENTED" is a
  genuine, correctly-documented limitation (no public Olo API, not a bug)
  -- confirmed this is still accurate, not something to build around.
- app/core/rate_limit.py's IP-vs-authenticated-user keying is a known,
  already-documented limitation (see its own module docstring and
  CRAVE_REMEDIATION_PLAN.md's security section) -- not new, not silently
  broken, correctly labeled as a deliberate follow-up.
- Backend-wide sweep for bare/silent excepts, SQL-injection-shaped string
  formatting, and frontend timer/listener leaks: all clean, nothing found.

Partial / needs your production access (unchanged from before):
- A3 (2 historical Square/Toast sources), A1 (13,148-place backlog run),
  A7 (source discovery), B1 steps 2/4 (real image fetch + hand-labeling).

Locked files: none currently held.
Verification plan: full backend suite green on every change (910
passed, 2 skipped as of this pass); every new/changed test independently
verified to catch its corresponding regression (temporarily reverted,
watched fail, restored) before merge -- same discipline as every prior
pass this session.
Next action: Codex, when back: (1) A1 backlog run, (2) A3 with actual
production row data, (3) B1 steps 2/4. Nothing from this sweep needs your
follow-up -- both real findings (IDOR, N+1) are already fixed and merged.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
