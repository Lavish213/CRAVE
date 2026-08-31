# E2 / E3 / E10 — product tradeoff docs (2026-08-31)

Three ambiguous UX/product questions from the Master Plan. Per its own
rule for this category ("product decision, lay out tradeoffs, don't pick
unilaterally"), these are option layouts, not recommendations pretending
to be neutral — no option below is silently favored in the code.

---

## E2 — Craves as active memory, not a bookmark list

### Current state (verified against the actual schema)

Two separate save paths exist, checked directly rather than assumed:

- **`CraveItem`** (`app/db/models/crave_item.py`) — the "share a link"
  import path. Already captures real provenance: original URL, source
  platform, oEmbed thumbnail/embed/author, matched place + confidence,
  retry/backoff on a failed match. This one's already close to doctrine
  §19's spec.
- **`HitlistSave`** (`app/db/models/hitlist_save.py`) — the direct "save
  this place" path. Captures place identity, source, resolution status —
  but **no visit state, no notes/tags, no dish-level link**. Doctrine
  §19 explicitly wants queries like "untried Craves" and "that pasta
  place I saved months ago" — neither is possible today because nothing
  records whether a saved place was ever actually visited, or what a
  user thought of it beyond the binary save/unsave.

### The gap, precisely

Not "Craves needs a rebuild" — the provenance/import side is already
solid. The gap is specifically: **no visited/untried state, no free-text
or tag annotation on a save.**

### Buildable now (schema, low-risk, additive)

Add `visited: bool` (default false), `visited_at`, and `notes: str |
None` to `HitlistSave`. Pure additive columns, no migration risk, no
existing query changes. This alone doesn't decide any UX — it just makes
the UX options below possible without a second schema change later.

### The actual decision: how does "visited" get set?

- **A — Explicit user action.** A swipe/long-press/button on a Craves row
  ("Mark as visited"). Most accurate, but adds a step nobody is asking
  for yet — doctrine's own anti-pattern list (#27, "fake personalization
  based on one click") warns against inventing interactions users don't
  organically want.
- **B — Inferred from an existing signal.** A save later gets ranked
  (the app already has a ranking/comparison flow) — ranking a place
  implies the user has been there. Zero new UI, but only covers users
  who use the ranking flow, and doesn't distinguish "visited, no
  opinion yet" from "visited and ranked."
- **C — Both, B as the default signal, A as an optional manual override**
  for someone who visited but hasn't (or won't) rank it yet.

### The actual decision: where do notes/tags surface?

- **A — Inline on the Craves list row** (a small text affordance,
  expands on tap). Fastest to reach, clutters a list that's currently
  clean.
- **B — Only inside a save's detail view** (tap into it, notes live
  there). Keeps the list clean, adds a tap to reach.
- **C — Free-text only, no structured tags** for now, since real tag
  taxonomy is its own design question (arguably as involved as the E8
  category taxonomy work) — ship notes first, decide tags later if
  people actually use notes heavily enough to want structure.

No option chosen here — this doc lays them out per the plan's own
standard.

---

## E3 — Video's missing home

### Current state (verified)

Grepped the whole frontend: `PlaceVideoGallery` is rendered in exactly
one place — `app/place/[id].tsx`. There is no feed action, no dedicated
tab, no surfacing anywhere outside a place's own detail screen. A video
someone records is essentially invisible unless another user happens to
open that exact place's detail page.

### Options

- **A — Feed action.** Feed cards get a "watch" affordance the way they
  already have save/rank actions — video becomes one more Feed
  interaction, not a separate destination. Reuses Feed's existing
  ranking/diversification instead of inventing a second content-ranking
  system. Risk: Feed's whole design principle (per doctrine's positioning
  section) is decision support, not content consumption — folding in
  video needs care not to turn Feed into "what looks exciting right now"
  (TikTok's lane, which doctrine explicitly says CRAVE should not become).
- **B — Own tab.** A dedicated video destination, closest to what most
  users will assume "record a video" implies. Highest build cost (new
  ranking/diversification logic, a whole new screen with its own empty/
  error states) and the most direct overlap with TikTok's actual lane —
  the doctrine risk from option A gets bigger here, not smaller.
- **C — Place Detail affordance only (status quo), invested in
  further.** Cheapest, zero new surface — just make what already exists
  more discoverable (e.g. a place with videos gets a visible badge on
  its Feed/Search/Map card, prompting a tap into detail rather than
  duplicating the content there). Doesn't solve "video has no home," but
  doesn't risk the TikTok-drift problem either.

Given B carries doctrine's own core risk (§2's explicit "must not become
Yelp+TikTok+Beli+Maps+AI") most directly, and zero video has gone through
the pipeline in production yet (per the last audit — B2 in the master
plan), **A or C are the lower-risk starting points** — but that's a
tradeoff observation, not a decision made here.

---

## E10 — Group / social decision-making

### Current state (verified)

Grepped both backend and frontend for any group-decision implementation
— zero matches. This is genuinely greenfield, and doctrine's own
architecture doc (§16, Group Compatibility) frames the actual algorithm
as unsolved ("a possible future objective," not a spec): "maximize group
satisfaction subject to hard constraints and minimum individual utility"
is stated as a direction, not something with a concrete formula yet.

### Why this is correctly last, not just arbitrarily deprioritized

Two real prerequisites, not just sequencing preference:

1. **The single-user Decision Session isn't proven yet.** Per the last
   production audit, ~5 outcome events total exist. Group mode is
   strictly harder than single-user (needs the same ranking signal,
   *and* a real conflict-resolution model on top) — building it before
   the foundation it depends on has any real usage data means building
   on an unvalidated base.
2. **Doctrine's own explicit warning**: "Group mode should reduce voting
   work, not turn dinner into Tinder for five people." A naive first
   version (everyone swipes, tally votes) is the easy build and the
   wrong one by this doctrine's own standard — it requires the harder
   hard-constraint/soft-preference distinction from day one, not as a
   v2 addition.

### If/when this gets picked up, lightest real starting points

Not full designs — just what avoids the "Tinder for five people" trap
doctrine warns about, in increasing order of complexity:

- **A — Host proposes, others veto.** One person runs Decision Session
  normally, gets 3 cards; the group can only knock a card out for a hard
  reason (allergy, budget, already-been-there), not re-rank by taste.
  Minimal new UI, no group-utility algorithm needed at all yet.
- **B — Shared hard constraints, single ranking.** Everyone's dietary/
  budget/travel constraints get collected once (not repeated swiping),
  intersected as hard filters, then Decision Session runs its existing
  single-user ranking against the filtered set. No group-utility scoring
  yet — just constraint aggregation, which is a much smaller problem
  than the full "maximize collective utility" objective.
- **C — Full group-utility ranking** (per doctrine's own stated
  objective) — the real long-term version, but only worth building once
  A or B have real usage proving people actually want a group flow at
  all.

No recommendation on timing beyond "not yet, and A/B before C if the
answer is ever yes" — consistent with the plan's own sequencing.
