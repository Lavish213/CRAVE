# Active agent state

Status: idle
Owner: Claude
Branch: main
Base SHA: 20e6941 (PR #91 merged)
Scope: A large end-to-end audit pass per the user's request to "search
project end to end for all gaps and bugs... check everything... pretend
to be user... fix or log" — covering a user walkthrough (incl. camera/
upload), a full schema audit, an accessibility re-verification, and 2
design/tradeoff docs (E8 taxonomy, E2/E3/E10). Still working solo since
Codex's session is offline; nothing here needed production access.

## Real fixes merged this pass (PRs #88, #89)

- **PR #88 — stuck photo uploads.** Found by walking the actual photo-
  upload flow end-to-end: `process_image_upload()` runs as a FastAPI
  BackgroundTask off `POST /upload/confirm`, with no durability (unlike
  video, deliberately moved to its own scheduler job for exactly this
  reason -- see `_job_video_processing`'s own docstring: "unlike
  photos"). A process restart/redeploy mid-task left the row stuck at
  'processing'/'pending' forever, with the frontend's status poll
  spinning indefinitely. Added `reclaim_stale_image_uploads()` +
  a new scheduler job (`image_processing_recovery`, every 10 min),
  mirroring video's existing self-healing pattern. 6 new tests.
- **PR #89 — modal backdrop accessibility.** A repo-wide re-scan for
  icon-only touchables found zero remaining gaps of that shape (PR #80
  already fixed the only 2). Found something related instead: 4 modal
  sheets (Filter/ShareLink/Auth/MenuSubmission) had an unlabeled full-
  screen backdrop Pressable sitting in VoiceOver's traversal order right
  before each sheet's own properly-labeled Close button. Fixed with
  `accessible={false}` on the backdrop (not a label -- would've been a
  second, confusing "close" announcement). Left `ReportPhotoSheet.tsx`
  alone -- its backdrop is the sole dismiss path there, already correctly
  labeled.

## Findings with no code change (verified, not guessed)

- **Schema audit (all 37 models)**: genuinely well-built. Every single
  ForeignKey in the schema has an explicit `ondelete` (confirmed via a
  script scanning every model file, zero gaps found). Indexing is query-
  pattern-matched (composite indexes matching real ORDER BY clauses, not
  blanket single-column indexing). Zero orphaned/unused model classes.
  Zero risky migrations (no NOT NULL column ever added without a
  server_default). One minor, non-urgent latent gap noted:
  `MenuSubmission.submitted_by` has no index, but nothing queries by it
  yet -- not worth a speculative index.
- **E8 (category taxonomy)**: corrected the Master Plan's own framing --
  `Category.type` (cuisine/venue/specialty) already exists in the
  schema, it's just completely unused end-to-end (not in `CategoryOut`,
  not anywhere in the frontend). Design doc at
  `docs/CATEGORY_TAXONOMY_DESIGN_2026-08-31.md` lays out a low-risk data
  fix plus 3 Filter-UI options, explicitly flagging the ownership/
  identity category grouping and the michelin_rated-as-a-category
  question as needing your call, not mine.
- **E2/E3/E10 tradeoffs**: doc at
  `docs/E2_E3_E10_PRODUCT_TRADEOFFS_2026-08-31.md`. E2: CraveItem already
  has rich provenance, HitlistSave is missing visited/notes state --
  concrete options laid out. E3: video is PlaceVideoGallery-only,
  confirmed by grep -- 3 options, flagging a dedicated tab as the
  highest-risk one (most directly overlaps TikTok's lane per doctrine's
  own positioning). E10: confirmed zero implementation exists anywhere;
  correctly last given Decision Session itself is still unproven (~5
  outcome events).

## Recap: PRs #82-#87 (previous consolidated update, still accurate)

Dead code cleanup (#82), a real IDOR fix on the upload status route
(#83), a real N+1 fix in menu_worker.py (#84), Codex's A3 diagnosis
reviewed and merged by me (#85), bridge reconciliation (#86 closed in
favor of #87).

Partial / needs production access (unchanged):
- A1 (13,148-place backlog run): safe to run, throughput bounded (PR
  #74) and the recompute N+1 fixed (PR #84).
- A3: diagnosis complete (PR #85). Both sources remain correctly
  unpublished pending a bounded, verified retry -- per Codex's own gate,
  do not retry until the deployed revision is confirmed (last known:
  Codex confirmed Railway deployed 95d9063, the PR #85 merge SHA, before
  its own session hit a usage limit mid-search for the bounded retry
  command).
- A7 (source discovery), B1 steps 2/4 (real image fetch + hand-
  labeling).

Locked files: none currently held.
Verification plan: full suite green on every change (926 backend passed/
2 skipped, 302 frontend passed, both confirmed on current main); every
new/changed test independently verified to catch its own regression
before merge -- same discipline the whole session.
Next action: Codex, when back: (1) finish locating the bounded A3 retry
command and run it only if the deployed SHA still matches, (2) A1
backlog run, (3) B1 steps 2/4. Nothing from this pass needs your
follow-up -- both real fixes (#88, #89) are merged, and the design docs
(E8, E2/E3/E10) are addressed to the user/team for a product decision,
not to you.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
