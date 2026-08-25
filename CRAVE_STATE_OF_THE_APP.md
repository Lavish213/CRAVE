# CRAVE — State of the App, Screen Audit, and Roadmap

Written as an honest snapshot, not a status report meant to look good.
Where something is weak, it's called weak. Where something is genuinely
solid, that's said plainly too — the point is calibration, not either
flattery or self-flagellation.

---

## 1. TL;DR

**CRAVE is engineering-solid and product-thin.** The backend has had a
level of rigor applied to it (race-condition fixes, idempotency,
migration discipline, CI gates, offline-sync correctness) that's
unusual for a pre-launch app — most of tonight's and recent sessions'
work has gone into making the *foundation* trustworthy: data doesn't
get double-counted, saves survive being offline, deploys don't silently
diverge, migrations don't corrupt production. That work was necessary
and it's genuinely done well.

What it is *not* yet: a product that feels smart, personalized, or
differentiated. Every screen functions. Almost none of them yet deliver
on the stated vision ("invisible intelligence" — Feed showing fewer but
stronger options, Craves resurfacing saved spots at the right time, Map
suppressing irrelevant pins, Search understanding intent). Right now
CRAVE is a competent, reliable restaurant-logging app with a clever
personal-ranking mechanic bolted on. The gap between "works correctly"
and "feels genuinely good to use" is still wide, and closing it is
design/product work that hasn't started in earnest — the screen-by-screen
polish pass has been on the plan for a while and keeps getting
deprioritized in favor of the next reliability fire.

That's not a criticism of sequencing — production correctness has to
come before product polish, or the polish sits on a foundation that
breaks under it. It's just where things actually stand.

---

## 2. Systems architecture, current state

**Backend**: FastAPI + SQLAlchemy + Alembic + Postgres (prod) / SQLite
(test fallback). Deployed on Railway, GitHub-integration auto-deploy
from `main`, `alembic upgrade head` runs as part of the start command
(migration-before-serve is structurally guaranteed, not a convention
someone has to remember). A separate `scheduler_worker` Railway service
runs APScheduler jobs (menu enrichment, image ingestion, city ranking,
video processing) off the request-serving process — this split exists
because of a real production incident where a scheduled job starved
live request handling.

**Frontend**: Expo/React Native (SDK 54), expo-router file-based
routing, Zustand stores, react-query for a few screens, axios client
with a Supabase-session-token interceptor. EAS builds for anything
touching native modules (camera, video) since the app can't run in
plain Expo Go anymore.

**Auth**: Supabase (JWKS-verified, asymmetric ES256 — this was broken
and fixed earlier this session; a static-secret HS256 check cannot
verify an asymmetric token no matter what the secret is).

**CI**: 5 checks on every push to `main` — conflict-marker guard,
backend (SQLite, syntax/import/tests/single-alembic-head), backend
(real Postgres, full migration chain + a downgrade/re-upgrade round-trip
on the newest migration + the same test suite), frontend (tsc + jest).
Not yet required as branch-protection gates — that's a GitHub dashboard
setting, still open.

**Data integrity patterns actually in place**, because each one was
earned by a real incident, not applied speculatively:
- Offline outbox + idempotency keys for anything that can retry after a
  crash (saves, video uploads) — a client-generated id lets a resent
  mutation or event become a harmless no-op instead of a duplicate.
- Fairness-reserve batching in background workers (image/menu
  enrichment) so a handful of high-rank places can't starve the rest of
  the catalog from ever being processed.
- `try/finally` around every Playwright browser handle after a real
  Chromium-process-leak OOM incident.
- Percentile-based tiering computed server-side per request (not
  cached/stale), because the underlying score distribution shifts as
  discovery adds inventory.

---

## 3. The actual screens, what they do, why, and an honest rating

Ratings are out of 10, "would a stranger who downloaded this app on
its own merits keep using it because of this specific screen." Not "is
the code good" — the code is frequently better than the product
experience it currently produces.

### Feed (`app/(tabs)/index.tsx`) — 6/10
The home tab. Infinite-scroll list, bucketed into tier sections (CRAVE
Pick / Hidden Gem / Worth Knowing / Explore) by each place's
city-percentile standing, not an absolute score — this was a real fix
this session (absolute-score buckets had clustered almost the whole
catalog into two tiers because of how the structural-signal score caps
work). "Recommended for You" and "Trending" strips exist in code but
are hidden (`SHOW_FEED_DISCOVERY_STRIPS = false`) on the reasonable
call that showing confident-looking personalization on top of
not-confident-enough data does more harm than good.

*Why this shape*: percentile tiering self-corrects as the catalog grows
instead of needing hand-tuned thresholds re-tuned every time discovery
adds inventory.

*Honest problems*: pagination is offset-based against a query that
reorders as new places get discovered every few minutes — not
corrupting anything (there's a dedup guard), but wasting real
round-trips, and it gets worse as discovery throughput increases. It's
been "next up" for two sessions running and keeps losing to more urgent
work. Also: the tier labels are the only "intelligence" a user sees —
there's no actual personalization live yet, so "Recommended for You"
being hidden is honest, but it also means the screen is currently just
a sorted list with nice section headers, not something that feels like
it knows you.

### Search (`app/(tabs)/search.tsx`) — 5/10
Had a real, live P0 bug this session: an out-of-range percentile from
data drift caused search results to silently vanish (`total` correct,
`items` empty) — root-caused and fixed via clamping. Works correctly
now. Basic keyword matching against place name/category, no query
understanding, no session modeling (about to be built — see §5).

*Honest problems*: it's a keyword filter, not search in any meaningful
sense. No typo tolerance evident, no intent parsing, no distinction
between "pizza" (a craving) and "restaurants near the airport" (a
constraint). This is squarely a "hasn't been designed yet" gap, not a
"the code is bad" gap.

### Place Detail (`app/place/[id].tsx`) — 4/10
The single highest-priority conversion screen by the product doctrine's
own account, and the one that has gotten the least deliberate design
attention. Functionally complete: hero image/gallery, tier badge, menu
(with submission flow), photo/video upload with a real moderation
pipeline, friend rankings, save, share, "I ate here" ranking entry
point. Every individual piece works and has test coverage.

*Honest problems*: it reads like a Yelp page — everything, in roughly
the order it was built, not the order a hungry person needs it
(identity → why this fits you → open/distance/price → what to order →
trust signals → menu → everything else). No design spec exists for
this screen yet; it's been flagged as the next real design task
multiple sessions running.

### Craves / Saves (`app/(tabs)/craves.tsx`) — 6/10
Bookmarked places + parsed share links (TikTok/Instagram food-content
matching). The offline outbox here is genuinely well-built — optimistic
add/remove, survives a killed app mid-sync, exponential backoff,
account-switch-safe, and (as of tonight) logs a Ledger event only on a
*confirmed* outcome, never a tap.

*Honest problems*: it's a static list. The doctrine's vision ("Craves
resurfacing saved spots at the right time") is not built at all — no
notion of "you saved this three weeks ago and you're nearby now,"
nothing. Right now Craves is a bookmarks folder with excellent
plumbing and zero intelligence.

### Map (`app/(tabs)/map.tsx` / `.web.tsx`) — 5/10
Bounding-box place query, had real performance work this session
(EXPLAIN ANALYZE-driven — isolated a 60-67s stall to the bulk category
lookup, not the base query). Preload/prefetch wired up.

*Honest problems*: it shows pins. No filtering intelligence, no
suppression of irrelevant results, nothing that distinguishes it from
any other map-of-restaurants. The "Map suppressing irrelevant pins"
vision is aspirational, not built.

### Personal Ranking / "I ate here" (`app/rank/[placeId].tsx`) — 7/10
The actual differentiating mechanic, and the most architecturally
sophisticated single feature in the app: binary-insertion comparison
("which was better") converging to a 0-10 score, with real replay
safety (a client retry after a lost response returns the
already-created ranking instead of erroring or duplicating). This is
where the engineering effort and the product idea are most aligned.

*Honest problems*: never confirmed working end-to-end on a real device
this session (or the one before) — everything here is proven at the
service/route-test level, not via someone actually tapping through the
comparison flow on a phone. That's a real gap for the single most
distinctive feature in the app.

### Video record/upload (`app/record-video/[placeId].tsx`) — 3/10
for actual current product impact, despite being a large, carefully
built pipeline (upload → compress → food-classifier score → thumbnail →
moderation → feed). Two structural problems, both already flagged
in-repo: (1) the food classifier model itself was "handed off
separately" — unclear if a real trained model is actually installed in
production or if this is degrading to its documented
model-unavailable fallback path; (2) discoverability is close to zero
— the only entry point is a small chip on Place Detail, nothing on Feed
or the tab bar. A feature nobody can find and that may not have a
working ML component yet is a 3/10 regardless of how well the plumbing
around it is built.

### Personal profile (`app/(tabs)/profile.tsx`, `taste-profile/[userId].tsx`) — unrated
Not deeply exercised or discussed this session — cross-referenced
research against Beli's own stats screen shape (total ranked, favorite
cuisines, top city) but no live-testing or design-critique pass has
happened here. Flagging the gap in this audit rather than guessing at
a number.

### Leaderboard / Friends Feed / Public profile (`leaderboard.tsx`,
`friends-feed.tsx`, `user/[id].tsx`) — 5/10
Social layer: ranked-by-places-logged leaderboard (a deliberate choice
— average-score ranking would just reward rating everything a 10),
chronological "your friend just ranked X" feed, someone else's profile
+ follow button. Functionally complete, sensible design choices
documented inline, but the whole social graph is only as good as its
network effect — with no real user base yet, this is infrastructure
waiting for people, not something to judge on its current
merits.

### Settings / Legal (`settings.tsx`, `legal/*.tsx`) — 7/10
Does its job: account deletion, push token management, in-app
privacy/terms screens grounded in what the app actually collects
(verified against real code, not boilerplate). Not a differentiator by
design — a utility screen being unremarkable is correct, not a flaw.

---

## 4. Recommendation Ledger / Decision Intelligence — current state

Phase 1 only, deliberately smaller than the full doctrine spec (no
algorithm version, candidate set, or reason codes — none of those exist
yet, since there's no ranking model to log them for).

**Built and production-certified with direct evidence tonight**:
impression/click logging on Feed, confirmed-outcome (not button-tap)
save/unsave logging with a client-generated idempotency key closing a
real double-log race, server-side completed-ranking-outcome logging
(reusing the existing replay guard, deliberately kept separate from
city-percentile data). A read-only debug endpoint
(`/api/v1/debug/recommendation-events`) makes checking this in
production a single HTTPS call instead of a console session.

**Genuinely still open**: whether the *app itself* reliably flushes its
batched events end-to-end in normal use — proven correct at the server
(a manually-constructed event round-tripped correctly), not yet proven
via an actual app tap in a stable (non-actively-reloading) session.
Search/Craves/Map instrumentation, deliberately not started — the
explicit call was to get save + ranking outcomes right first, since
they're stronger signal than a wall of impressions.

---

## 5. Design logic worth stating explicitly (so it doesn't get relitigated later)

- **City-percentile tiers and personal taste are different truths and
  must never be conflated.** A place's tier answers "how good is this,
  objectively, in this city" — never "is this good for you
  specifically." As personalization gets built, this line has to hold.
- **Log confirmed domain outcomes, not UI intent.** A tap isn't a save;
  a save is a save. This is why the Ledger's save/unsave logging waits
  for a confirmed backend outcome (immediate or offline-outbox-flushed)
  rather than firing on tap.
- **Search intent ≠ taste evidence.** Searching "vegan restaurant for a
  friend" should not be read as "this user loves vegan food." A search
  becomes real taste evidence only once followed by an action (detail →
  save, or detail → positive ranking) — this governs how Search
  instrumentation gets built next, not a raw per-keystroke firehose.
- **Make invalid states structurally impossible, not documented
  around.** `getTierForPlace()` replacing a two-argument
  easy-to-misuse `getTier()` is the reference pattern; the same
  treatment is owed to whatever screen-state and upload-visibility
  helpers come next.
- **Fix the root cause, not the symptom.** The Chromium-leak fix wasn't
  "restart the container more often" — it was `try/finally` at every
  call site actually launching a browser process. The menu-worker
  starvation fix wasn't "raise the batch size" — it was a fairness
  reserve.
- **A retry must preserve identity, not become a new event.** Every
  idempotency key in this app (video upload's `client_id`, the
  Ledger's `client_event_id`) is minted once at the start of a logical
  action and reused across every retry of that same action — never
  regenerated per attempt.

---

## 6. Full remaining work, prioritized

**P0 — process/reliability, self-executable or near it**
- [ ] Require the 5 CI checks as branch-protection gates on `main`
      (GitHub dashboard setting).
- [ ] Confirm the app's real save/unsave flush works in a stable
      (non-reloading) build — the one open item from tonight's
      verification.
- [ ] Fix the FK-violation-vs-dedup-race ambiguity in
      `record_events`'s IntegrityError fallback (cosmetic-severity,
      found during tonight's verification).
- [ ] Rotate `API_KEY` — the same value has now been pasted into this
      chat transcript twice.

**P1 — needs a human decision or a device**
- [ ] Physical-device smoke pass (Launch/Auth/Feed/Search/Place
      Detail/Save/Map/Upload/Offline/Push) — push notification
      especially, since it's never been confirmed delivered to a real
      device.
- [ ] Record-video discoverability — product decision (a context-aware
      Feed action or a prominent Place Detail affordance, not a
      TikTok-style tab, until usage actually proves creation deserves
      global nav real estate).
- [ ] Confirm whether the food-classifier model is actually installed
      and running in production, or silently degrading to its
      fallback path.
- [ ] Rank/comparison flow — actually exercise it end-to-end on a real
      device; it's the app's core differentiator and has never been
      watched work live.

**P1 — design, not yet started**
- [ ] Place Detail redesign spec (hero identity → why this fits →
      open/distance/price → what to order → trust signals → menu →
      full details) — the highest-priority screen with the least
      design attention.
- [ ] The screen-by-screen §33-rubric / anti-slop audit against the
      product doctrine that's been queued for several sessions.

**P1/P2 — architecture, needs its own evidence pass**
- [ ] Feed cursor/keyset pagination — do NOT jump straight to this;
      first instrument and confirm deterministic ordering, then decide
      if keyset actually buys enough to justify the retrieval-layer
      change.
- [ ] A typed `DiscoveryQuery` contract shared by Feed/Map/Search, so
      the same filters can't silently mean different things per screen.

**P2 — Recommendation Ledger fast-follows, in order**
- [ ] Search-session instrumentation (query/session id, results shown +
      position, selection, reformulation — not per-keystroke).
- [ ] Craves instrumentation (save resurfacing, "picked from Craves"
      outcomes).
- [ ] Map instrumentation (marker selection / place-detail transition,
      not raw marker impressions — those are noisy).

**P2 — launch readiness**
- [ ] App Store: hosted Privacy Policy URL (separate from the in-app
      screen), Apple Developer Program membership, screenshots/metadata,
      permission-copy review.
- [ ] Visual regression / E2E coverage — currently zero. Start with 3
      journeys (Feed→Detail, Search→Detail, Save→Craves→Detail), not a
      19-screen suite.

**P3 — after real usage data exists, not before**
- [ ] Taste modeling / learned ranking / risk engine — everything past
      "Gate 1" event logging in the decision-intelligence doctrine.
      Deliberately waiting on real behavioral data rather than building
      ahead of it.
- [ ] Splitting the 32-flat-category taxonomy into real dimensions
      (cuisine / meal-period / dietary / experience / ownership) — fine
      today, will become a real constraint on Search/filtering/
      personalization eventually.

---

## 7. If I had to say it in one paragraph

The infrastructure is trustworthy enough now to build real product on
top of without it collapsing — that wasn't true a few sessions ago, and
it is now, verified with tests and live evidence rather than assumed.
But CRAVE the *product* still reads as a well-engineered restaurant
catalog with one genuinely clever mechanic (personal ranking) buried in
it, not yet the "invisible intelligence" experience the doctrine
describes. The next real unlock isn't another reliability fix — it's
someone actually sitting down and designing Place Detail, watching a
real person use the ranking flow, and deciding what Feed should feel
like once it has real signal to work with. That work hasn't started
yet, and no amount of backend hardening substitutes for it.
