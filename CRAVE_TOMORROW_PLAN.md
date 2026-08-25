# CRAVE — Plan for Tomorrow

Ordered by priority. Don't start P1 until P0 is actually confirmed fixed —
everything downstream assumes the app works at all.

---

## P0 — Broken right now, fix first

### 1. Search returns 0 results for every query
Confirmed live: `total` count is correct (backend finds real matches),
but every result silently fails to serialize, so `items` is always empty.
Not reproducible locally against equivalent test data — something specific
to the production environment/data.

- Logging was fixed last (commit `fca764e`) so the real exception will
  now actually appear in Railway's logs instead of being silently
  swallowed at debug level.
- **First step:** confirm this commit is actually deployed (`git pull` +
  `railway up` from `backend/`), search for anything, then check
  Railway's dashboard → Logs tab for `search_serialize_failed` — the
  traceback will say exactly what's throwing.
- Once the real error is visible, this should be a fast, well-targeted
  fix rather than more guessing.

### 2. Confirm which commits are actually live in production
Multiple backend commits landed this session (JWT/JWKS auth fix,
percentile-based tiering, the logging fix). Only confirmed one Railway
deploy explicitly. Before doing anything else:
```bash
cd ~/crave/backend
git log --oneline -1                 # should show fca764e or later
git pull --ff-only origin claude/project-grade-systems-review-4ot7d0
railway up
```
Then re-verify end to end:
- Sign in with `lordandangels@gmail.com` — should work fully, including
  profile setup (no "Invalid token").
- Search screen — tier badges should show a real spread (CRAVE Pick /
  Hidden Gem / Worth Knowing / Explore), not just two tiers.

### 2.5 Feed pagination drift (confirmed, not broken, but real waste — worsening over time)
Traced from live logs showing pages returning 0-1 new items while
`total` stayed at 13273. Root cause, confirmed by reading
`app/(tabs)/index.tsx:116-126`: Feed paginates by offset against a query
ordered by `rank_score`, not a stable cursor. A background discovery
pipeline inserts new places every 5 minutes, shifting the offset window
between page fetches, so the same place can land in both an
already-loaded page and the next one. There's already a client-side
dedup guard (added after a real duplicate-key crash) that correctly
filters these out — so this is not silently corrupting data or crashing,
it's *wasting* round-trips: each subsequent page fetch spends most of
its `limit` re-fetching stuff already seen. The code comment notes the
discovery pipeline "now processes a growing OSM/Overture backlog faster
than before this session" — insert rate is rising, so this gets worse
over time, not better. Real fix: cursor-based (keyset) pagination
instead of offset — a genuine backend change, worth scheduling
deliberately rather than leaving to keep degrading.

---

## P1 — Real gaps found via live testing today

### 3. Photo/menu contribution permissions — DONE
Turned out smaller than originally scoped: `upload_moderation.py` already
had a real, sophisticated content-moderation pipeline (quality/safety/
GPS-trust scanning, auto-reject/hold-for-review/auto-publish) — the gap
was specifically the *identity* dimension, not content safety. Any
signed-in user's good-quality, safe photo auto-published regardless of
who they were.

Built:
- `app/core/contributor_access.py` (new) — shared `is_admin()` /
  `is_trusted_contributor()`, backed by `ADMIN_USER_IDS` (existing) and a
  new `TRUSTED_CONTRIBUTOR_USER_IDS` env-var allowlist. `moderation.py`'s
  `require_admin` and `app/scheduler.py`'s health check now both delegate
  to this instead of moderation.py's own private copy.
- `upload_moderation.py::screen_upload` — added a contributor-tier gate as
  the *last* step: an upload that would otherwise auto-publish (`MOD_APPROVED`)
  now gets held for human review (`MOD_PENDING_REVIEW`, reason
  `"untrusted_contributor"`) unless the uploader is admin/trusted. A photo
  that actually fails quality/safety is still rejected outright regardless
  of who uploaded it — trust only ever affects the approve branch. Since
  "Add menu photo" shares the exact same upload/moderation pipeline (the
  menu-OCR step only runs after this gate, on already-published photos),
  one change covers both photo types.
- `moderation.py::review_image` — now sends a push notification on
  approve/reject, mirroring the existing video-review notification
  pattern exactly (`"Your photo is live!"` / rejection copy).
- Tests: `test_contributor_access.py` (new, 11 tests), 3 new tests in
  `test_upload_moderation.py` covering the gate itself, plus fixed 8
  tests that had encoded the *old* intended behavior (plain user always
  auto-publishes) — now correctly require explicit trust for what they're
  actually testing (quality/safety pipeline, primary-image election), not
  silently broken by the identity change.

Still open, lower priority — genuine UX polish, not launch-blocking:
- Frontend button copy still says "Add photo"/"Add menu photo" for
  everyone; a non-privileged user's tap now correctly gets held for
  review, but the button doesn't yet say "Suggest a photo" to set that
  expectation up front. Requires the frontend to know the current user's
  tier (a new field on the user profile response) — real but small
  follow-up work, not done tonight.
- No "was this actually used as the place's photo, not just approved"
  flag yet for the notification — currently notifies on the moderation
  decision itself (matches the existing video pattern), not on a later
  "did this specific photo end up as the display image" event.

### 4. Record-video has no discoverable entry point
Confirmed: the only way to reach video recording is tapping into a
specific place's detail page and finding a small "Record a video" chip.
Nothing on the Feed screen or tab bar. For a feature this central,
that's a real discoverability gap worth a product decision — a tab bar
icon, a FAB on Feed, something. Not a bug, but worth deciding on
deliberately rather than leaving as-is by accident.

---

## P2 — Known, deferred, needs doing before real users show up

### 5. Live device testing of the full video pipeline
Record → upload → moderation → push notification is built and unit
tested but has never been exercised end to end on a real device with a
real video. Do this once search and permissions are stable.

### 6. Railway deploy hardening
`railway up` currently uploads your local working directory directly —
no GitHub connection, no commit history, no way to know what's actually
deployed without checking manually (which is exactly what bit us in P0
#2). Worth switching to GitHub-connected auto-deploy so a deploy is
always traceable to a specific commit.

### 7. App Store submission prep
- Privacy Policy needs a real **hosted URL** for App Store Connect — the
  in-app screen (`legal/privacy.tsx`) is good but isn't a substitute for
  that separate requirement.
- Apple Developer Program membership needed for anything beyond
  simulator builds (real device testing, TestFlight, submission).

---

## P3 — Worth doing, lower urgency

### 8. Gate 1 event logging (from the Decision Intelligence architecture doc)
Just the observability foundation — `recommendation_session_started`,
`candidate_impressed`, `candidate_selected`, etc., with algorithm version
and visual position on every row. Cheap to add now, expensive to
retrofit after real usage starts. Everything past Gate 1 in that doc
(taste modeling, risk engine, learned ranking) should wait for real
behavioral data — don't start those yet.

---

## P1.5 — Screen-by-screen polish pass before launch (explicit priority)

Two doctrine docs now live in `docs/doctrine/`: `CRAVE_DECISION_INTELLIGENCE_ARCHITECTURE.md`
(ranking/recommendation engine spec) and `CRAVE_MASTER_PRODUCT_INTELLIGENCE_BIBLE.md`
(product/UX doctrine — screen-by-screen purpose, anti-slop banned list,
100-point audit rubric in its §33). Confirmed priority: screens need to
be genuinely better before launch, not just functional.

Concrete next step: run each of the five core screens through the
Bible's §33 rubric and §31 anti-slop checklist against the actual
current implementation — not the doctrine in the abstract, the real
components as they exist today. That audit produces the actual punch
list; don't skip straight to redesigning without it. The Bible's own
§22-26 already name specific live issues to verify (Feed's weak
recommendation chips, Map's marker-noise problem, Search's empty
zero-state, Craves as a plain bookmark list, You's vanity counters) —
check whether those are still true of the real code before assuming
they are.

**Screen order** (per follow-up strategic review): Search → Feed →
Place Detail → Filters → Craves → Map → You → onboarding/ranking.
Place Detail specifically should get more attention than it's had —
it's the actual conversion point between "interesting" and "I'm eating
here."

**Place Detail: audited (2026-08-25).** Found and fixed two real bugs:
the upload-confirmation toast always said "Photo added" even for a photo
silently held by the contributor-tier gate (the status-poll endpoint
didn't expose `moderation_status`, only the processing-lifecycle
`status`, which reaches "ready" either way); and the screen's own tier
badge was calling `getTier(place.rank_score)` without the
`rank_percentile` arg, a missed call site from the percentile-tiering
rollout (same bug also found and fixed in Feed's section bucketing).
Full details in `CRAVE_REMAINING_WORK.md`. Filters → Craves → Map → You
still unaudited.

Full ranking/taste-graph/event-ledger buildout from both docs is real
work but should follow the build order both docs already specify (hard
constraints and catalog truth before personalization, personalization
before learned ranking) — not be pulled forward ahead of the screen
polish pass or the P0/P1 items above.

### Two guardrails to hold onto as this gets built out

- **Percentile tiers ≠ personalization.** City-percentile standing
  (CRAVE Pick / Hidden Gem / etc.) answers "how good is this place,
  objectively, relative to its city" — it must never quietly start
  answering "is this good *for this specific user*." Those are different
  signals; keep them architecturally separate as personalization gets
  built, per both doctrine docs.
- **The 32 flat categories are not a permanent ontology.** Live data
  already mixes cuisine (Japanese, Mexican), meal period (Breakfast),
  dietary (Vegan, Gluten Free), experience/format (Fine Dining,
  Romantic), and ownership (Black Owned, Woman Owned) in one flat list.
  Fine for now, but Search, filtering, and any real personalization will
  need these split into separate dimensions eventually — don't build
  deep dependencies on the flat list assuming it's final.

## Suggested order tomorrow

1. Confirm deploy state, fix search (P0).
2. Decide on record-video discoverability (P1 #4) — quick product call,
   cheap to implement once decided.
3. Scope and build the photo/menu permission system (P1 #3) — the
   biggest real chunk of new work.
4. Live device pass on video (P2 #5) once the above are stable.
5. Railway/App Store prep (P2 #6-7) whenever you're ready to move toward
   an actual submission.

## Frontend architecture roadmap (post screen-audit, post getTierForPlace)

Written after `getTierForPlace()` shipped as the reference pattern for
"make an invalid state impossible instead of documenting around it."
Ten follow-on ideas, roughly in the order they'd pay off — not urgent,
not blocking, but worth returning to once the P0 production issues are
resolved:

1. **"Make invalid states impossible" pass across the rest of the
   frontend** — same treatment as `getTierForPlace()` for every other
   place the guide documents as "easy to violate": stale-response
   guards, moderation-vs-processing status, offline outbox semantics.
   Look for typed helpers that make the mistake a compile error instead
   of a comment.
2. **Canonical screen-state helper** (loading / content / empty / error
   / refreshing / offline_cached) — a shared typed pattern, not a new
   state library, so screens stop each reinventing this slightly
   differently.
3. **Visual regression coverage** — none exists today; layout changes
   are verified by eye. Belongs on the roadmap before a real Feed/Place
   Detail/Filters/Craves/Map/You redesign push, not before it.
4. **A typed recommendation presentation contract** (reason codes,
   tradeoff codes, role, confidence, dish, place, context) — defined
   *before* the Recommendation Ledger and Feed redesign start inventing
   bespoke props screen-by-screen. `PlaceOut` is still place-centric;
   this would sit alongside it, not replace it.
5. **Audit `normalizePlaceOut()` as a strategic choke point** — it's the
   one place a backend field can silently vanish before reaching a
   screen. Contract tests around `rank_percentile`, `categories`,
   `price_tier`, `primary_image_url`, and future fields (open_status,
   recommendation reasons) would catch silent drops.
6. **Keep tier identity (`crave_pick`/`gem`/`solid`/`new`) and display
   copy (CRAVE Pick / Hidden Gem / ...) strictly separate** — never
   branch UI logic on the label. One canonical mapping only.
7. **Debug-only "Why am I seeing this?" inspector** — long-press a
   recommendation in dev to see candidate source, percentile, distance,
   active filters, reason codes, algorithm version. Not user-facing;
   pure tuning/debugging leverage once ranking work gets serious.
8. **A single typed `DiscoveryQuery` contract** shared by Feed/Map/Search
   filtering — the risk being silent semantic drift (Feed says 18
   results, Map shows 42, Search shows 11, each screen having quietly
   interpreted the same filters differently).
9. **Place Detail design spec** (no code yet) — it's already flagged as
   the highest-priority conversion screen. Define the information order
   before touching visuals: hero identity → why this fits → open/
   distance/price → what to order → social/trust → menu → full details.
   Prevents a Yelp-style everything-everywhere page.
10. **One hygiene rule for the guide itself**: once a helper encodes a
    domain invariant, screens must call it instead of re-deriving the
    logic locally. `getTierForPlace()` is the model; the same idea
    applies to whatever `getUploadVisibilityState()` /
    `getRecommendationRole()` / `getFilterCount()` end up looking like.

**Bigger-picture framing, beyond any single item above:** the next phase
of CRAVE should feel like "invisible intelligence" rather than "added AI
features" — Craves resurfacing saved spots at the right time, Map
suppressing irrelevant pins, Feed showing fewer but stronger options,
Search understanding intent, You explaining learned taste. The product
should feel sharper, not more instrumented.

**Suggested sequencing for all of this:** production truth + Search
first, then Feed retrieval, then Recommendation Ledger/event contracts,
then the Place Detail design spec, then DiscoveryQuery/filter
unification, then visual regression tooling. Reliability and a clean
foundation before the bigger product upgrades — consistent with this
plan's existing "hard constraints before personalization" ordering
above.
