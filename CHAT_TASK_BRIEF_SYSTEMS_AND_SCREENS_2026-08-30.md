# Task brief for Codex — systems + screens, 2026-08-30

This is the full "make everything better" list, not a scoped sprint.
Sequenced so real, buildable work happens before speculative/architectural
work. Some of this overlaps `CHAT_TASK_BRIEF_2026-08-30.md` (still
in-flight as of this doc — the Oakland entity-review apply) — don't
duplicate that work, just continue it.

**Ground rules, same as always:**
- `.agent-bridge/` protocol: claim in `STATE.md`, write handoffs to
  `codex-to-claude.md`, never touch `claude-to-codex.md`.
- **Research before building on anything marked 🔬.** Read the relevant
  doctrine doc section, check what's already true in the codebase, and
  propose the approach in your handoff before writing code. Silently
  picking the first reasonable-looking design is not acceptable for these
  — they're either genuinely ambiguous or expensive to redo if wrong.
- Every handoff claim independently verifiable — exact commands, exact
  output.
- Nothing touching production ships without the same staged/reversible/
  exact-confirmation pattern already established (PRs #61, #64).

---

## Part A — Systems (backend / data / intelligence)

### A1. 🔬 Personalization — do NOT start building yet
Tiers are city-percentile ("how good is this place"), never "is this
good for you." The full design already exists in
`docs/doctrine/CRAVE_MASTER_PRODUCT_INTELLIGENCE_BIBLE.md` §5 (signal
hierarchy, user taste graph, time horizons) and
`CRAVE_DECISION_INTELLIGENCE_ARCHITECTURE.md` §6-7. **This is explicitly
gated on having real usage data** — check whether enough event/behavior
data now exists (Recommendation Ledger has been live for a while) to
even start, and report that finding before writing any model code. If
there isn't enough real signal yet, say so and stop — don't build on
synthetic assumptions.

### A2. 🔬 Ranking beyond a single score
Architecture doc §9-14 specs choice-utility prediction, exploration/
exploitation balance, diversity re-ranking, and a risk/confidence layer.
Same gate as A1 — report on data readiness before designing anything.

### A3. Search intent parsing
No typo tolerance, no "cheap tacos open late" parsing. Unlike A1/A2,
**this does not need to wait for usage data** — it's a scoped, buildable
project today. Research existing options (Postgres trigram/fuzzy search
vs. a lightweight intent-parsing layer) before picking one; report the
tradeoff, then build.

### A4. 🔬 Category taxonomy split
32 flat categories mix cuisine/meal-period/dietary/experience/ownership.
Fine today, will constrain filtering as volume grows. Research what a
real multi-dimension taxonomy looks like for a restaurant-discovery app
(check what similar products do — doctrine §36 has competitive notes)
before proposing a schema migration. This touches every place row —
migrate carefully, in bounded batches, same discipline as the population
canary work.

### A5. Ongoing data-quality process (not one-time)
The Overture entity-review process built for the Oakland canary needs to
become a repeatable process, not a one-off script, before any other city
gets populated. Document what would need to change to run this for a
second city — don't just copy-paste the Oakland script with new
coordinates.

### A6. Group/social decision-making
Architecture doc §16, "group compatibility" — deciding where to eat when
multiple people's tastes are in play. Nothing built yet. Lowest priority
in Part A; don't start until A1-A4 are further along.

---

## Part B — Screens (frontend / UX)

### B1. Place Detail polish (highest priority in Part B — closest to done)
Scored 77-79/100 against `docs/doctrine/CRAVE_PLACE_DETAIL_SPEC.md`'s
§33 rubric, target 85+. Every remaining point is a device/screenshot
judgment call, not more code — take real simulator/device screenshots
first, compare against the rubric's specific line items, then fix only
what's visibly wrong. See `CRAVE_REMAINING_WORK.md`'s 2026-08-26 entry
for the last pass's category breakdown before starting.

### B2. 🔬 Craves — make it active, not a bookmark list
The doctrine's retention flywheel (§38) assumes saved places resurface
at the right moment — before a decision, not just sitting in a list.
Research what "the right moment" means concretely (time of day? distance
from a saved place? a Feed re-surfacing rule?) and propose the mechanism
before building it.

### B3. 🔬 Video's missing home
Record has no discoverable entry point beyond a small Place Detail chip.
Three options exist — Feed action, Place Detail affordance, its own tab.
This is a product decision: lay out how each option affects the existing
nav structure and Feed/Place Detail layouts, with tradeoffs, and bring
options back. Don't build any of them yet.

### B4. Map/Search "search this area" sync
Panning the map doesn't cleanly sync with Search yet — flagged as
unfinished even after this session's clustering fix (PR #57). Scoped and
buildable; research the current Map/Search state coupling before wiring
this up.

### B5. Empty-state and error-state audit
Doctrine §42 specs empty states deliberately; most of this session's
error-vs-empty fixes were reactive bug fixes, not a designed pass. Audit
every screen against §42 and report gaps before fixing anything — this
is a research/report task first.

### B6. Accessibility audit
Doctrine §33.I tracks this in the rubric; no dedicated pass has happened.
Screen-reader labels, contrast, tap targets — audit and report findings
first, fix only what's confirmed broken (some of this may already be
covered opportunistically from other fixes this session).

### B7. Onboarding / cold-start review
Both doctrine docs (§18 architecture, and the Bible's cold-start section)
specify what a brand-new zero-signal user should see. Compare against
what actually happens today and report the gap — don't assume it's
broken, verify first.

---

## Sequencing

1. Finish what's already in flight (`CHAT_TASK_BRIEF_2026-08-30.md`'s 8
   items, especially the Oakland entity-review apply).
2. B1 (Place Detail) and A3 (search intent) — concrete, buildable, no
   research gate.
3. A5 (repeatable data-quality process) — needed before any other city
   gets populated.
4. B4, B5, B6, B7 — scoped audits/fixes, moderate effort.
5. A1, A2 (personalization/ranking) — only after confirming real usage
   data actually supports it. This is the biggest, most consequential
   work in this whole doc — do not rush into it.
6. B2, B3, A4, A6 — product decisions and larger builds, pick up as
   capacity allows.

## Reporting back

Same as every prior handoff: exact commit SHA, exact commands + output,
known gaps stated plainly, next action named. Claude independently
re-verifies everything before any merge.
