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

---

## P1 — Real gaps found via live testing today

### 3. Photo/menu contribution permissions
Right now any signed-in user can upload a place photo or menu photo
directly, no review. You want that restricted to admin/staff/trusted
contributors (e.g. influencers), with everyone else going through a
"suggest a photo" flow that an admin reviews, with a notification if
their submission gets used.

You already have most of the pattern built — `menu_submissions.py`
implements exactly this shape (submit → pending → admin review →
approve/reject) for menu *text*, gated by `require_admin` (an
`ADMIN_USER_IDS` env-var allowlist in `moderation.py`). Photos have no
equivalent.

Scoped work:
- Extend the admin allowlist into a real trust-tier concept (not just a
  flat env var) — admin / staff / trusted contributor.
- Gate `upload.py`'s direct photo upload the same way menu submission
  gates menu text: privileged tiers write directly, everyone else's photo
  goes to a review queue instead.
- New `PhotoSubmission` model/migration mirroring `MenuSubmission`.
- Admin review endpoints, reusing the existing moderation queue pattern.
- Push notification on approval (plumbing already exists from earlier
  this session) — needs a real "was this actually used as the place's
  photo" flag, not just "approved."
- Frontend: regular users see "Suggest a photo" instead of "Add photo";
  privileged users keep the direct button.

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

Two doctrine docs are now in context: `CRAVE_DECISION_INTELLIGENCE_ARCHITECTURE.md`
(ranking/recommendation engine spec) and `CRAVE_MASTER_PRODUCT_INTELLIGENCE_BIBLE.md`
(product/UX doctrine — screen-by-screen purpose, anti-slop banned list,
100-point audit rubric in its §33). Confirmed priority: screens need to
be genuinely better before launch, not just functional.

Concrete next step: run each of the five core screens (Feed, Map,
Search, Craves, You) through the Bible's §33 rubric and §31 anti-slop
checklist against the actual current implementation — not the doctrine
in the abstract, the real components as they exist today. That audit
produces the actual punch list; don't skip straight to redesigning
without it. The Bible's own §22-26 already name specific live issues to
verify (Feed's weak recommendation chips, Map's marker-noise problem,
Search's empty zero-state, Craves as a plain bookmark list, You's vanity
counters) — check whether those are still true of the real code before
assuming they are.

Full ranking/taste-graph/event-ledger buildout from both docs is real
work but should follow the build order both docs already specify (hard
constraints and catalog truth before personalization, personalization
before learned ranking) — not be pulled forward ahead of the screen
polish pass or the P0/P1 items above.

## Suggested order tomorrow

1. Confirm deploy state, fix search (P0).
2. Decide on record-video discoverability (P1 #4) — quick product call,
   cheap to implement once decided.
3. Scope and build the photo/menu permission system (P1 #3) — the
   biggest real chunk of new work.
4. Live device pass on video (P2 #5) once the above are stable.
5. Railway/App Store prep (P2 #6-7) whenever you're ready to move toward
   an actual submission.
