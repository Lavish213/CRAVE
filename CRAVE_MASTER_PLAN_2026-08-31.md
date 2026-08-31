# CRAVE — Master Plan (2026-08-31)

Single consolidated reference superseding `CHAT_TASK_BRIEF_2026-08-30.md`
and `CHAT_TASK_BRIEF_SYSTEMS_AND_SCREENS_2026-08-30.md` (fold their still-
open items in here; don't work from those two anymore). Every claim below
was checked against the actual code before being written down — where I
was wrong in an earlier conversation, it's corrected here, not repeated.

**Ground rules, unchanged:**
- `.agent-bridge/` protocol: claim in `STATE.md`, write handoffs to
  `codex-to-claude.md`, never touch `claude-to-codex.md`.
- 🔬 = research/verify before building. Don't guess; check what already
  exists first — this doc exists because two prior "gaps" turned out to
  already be solved in code nobody had re-checked.
- Every handoff claim independently verifiable — exact commands, exact
  output.
- Nothing touching production ships without staged/reversible/exact-
  confirmation gating (established pattern: PRs #61, #64, #71).
- Menu extraction is free-route only, now enforced in code (PR #71) —
  `allow_llm_fallback` must stay `False` from any bulk/scheduled path.

---

## Part 0 — Corrections to earlier advice in this session

Stated for the record so nobody re-does solved work:

- **"No scheduler running" was a false alarm.** It runs in a separate
  Railway project (`rare-sparkle`), confirmed at process/service/log/
  `JobRun`-row layers. Do not investigate this again.
- **"Add sitemap/menu-page discovery" was redundant** — it already exists
  and is already live. `extraction_controller.py::_discover_menu_pages()`
  (called from `menu_orchestrator.py`, the real production path) already
  tries common menu paths (`/menu`, `/order`, etc.), then homepage
  nav-link scanning via `menu_discovery_engine.find_menu_links()`, then
  schema.org `hasMenu`. This was proposed as a new idea two messages ago
  in this session — it was wrong; don't build it again.

---

## Part A — Menu coverage (highest near-term leverage)

Baseline: 37,761 active places, 985 with menus (**2.6%**). 13,148 have a
real source and have simply never had extraction run. 23,628 have no
known source at all.

### A1. Run the existing pipeline against the 13,148 backlog
No new code. This is the single biggest lever — the free-tier plan
projects 10-40%+ total coverage from this alone, depending on success
rate. Must be profiled/bounded first (A2) before scaling.

### A2. Profile and bound menu-enrichment throughput
Already flagged by Codex: one observed run exceeded 17 minutes, mostly
burned on low-yield generic API-endpoint probes. Needs per-domain time
budgets and yield tracking before raising batch size or concurrency.
**Do this before A1's bulk run, not after.**

### A3. Fix the 2 historical Square/Toast sources that never published
Already-sourced, already-adapted, silently failing. Cheapest possible
win — investigate the actual cause before retrying blindly.

### A4. Add a BentoBox provider adapter
🔬 Verified real gap: `app/services/menu/providers/` has adapters for
Toast, Square, ChowNow, Popmenu, Clover, Olo, Grubhub — no BentoBox,
despite it being on the free-tier plan's own target list. BentoBox sites
currently fall through to generic HTML/hydration/JSON-LD only. Research
BentoBox's actual page structure (JSON-LD support? embedded state?)
before building a dedicated adapter — don't assume it needs the same
shape as the others.

### A5. 🔬 Menu-photo OCR extension — later phase, not now
`app/services/menu/ocr/menu_photo_ocr.py` exists and works, but only
fires on user-uploaded photos (wired into `upload.py` and
`image_processing_worker.py`), not the bulk pipeline. Extending it to
existing place images depends on first solving "is this photo actually a
menu" — the same weak-signal problem already flagged in Part B. Do not
start this before B1 has a real answer; sequence it after.

### A6. Dead-code cleanup candidates (verified zero callers, low priority)
`menu_link_finder.py`, `menu_link_discovery.py`, and `menu_site_crawler.py`
are entirely unused — confirmed via repo-wide grep, zero imports anywhere.
They appear to be an earlier, superseded implementation of what
`extraction_controller.py` + `menu_discovery_engine.py` now do live. Safe
to delete once someone confirms they're not a deliberate reference kept
for a reason; not urgent, don't block other work on this.

### A7. 🔬 Source discovery for the 23,628 unsourced places
Real, separate project — OSM/Wikidata website tags, official-site search.
Lower priority than A1-A4 since the sourced backlog alone gets most of
the projected gain. Research actual free data availability (OSM coverage
rate for these specific places) before committing to a scope.

**Sequencing: A2 → A3 → A1 → A4 → A7 → A5.**

---

## Part B — Image coverage

77,701 images with unknown Phase 3 content classification. A prior dry-
run heuristic was tried and correctly rejected (90.3% unknown — mostly
encoded URL/position guesses, not real visual signal).

### B1. 🔬 Design a real byte-based classification holdout
Not a rerun of the positional heuristic. Needs an actual experiment
design (sample size, ground-truth labeling method, what "classified"
means) before any code — this is a research task first, explicitly.

### B2. Food-classifier production status: confirmed installed, unproven live
Not broken — genuinely just unexercised (zero `PlaceVideo` rows in
production to run inference against). Closing this needs a real device/
integration test with an actual upload, not more code.

---

## Part C — Confirmed infrastructure (no action needed)

- **Scheduler**: running correctly in a separate Railway project. Verified
  multi-layer. Do not touch.
- **Free-route lock**: `allow_llm_fallback` is now independently
  controlled and locked off from the orchestrator's call site (PR #71),
  with 3 tests (2 direct, 1 AST static guard) each confirmed to fail
  without their corresponding fix. Menu-source success is now recorded
  only after `MenuPublisher.publish()` actually persists ≥1 item (PR #68)
  — no longer marked "success" on mere extraction.
- **Placeholder menu cleanup**: tooling exists (preview/simulate/apply,
  exact confirmation), 3 rows identified. Apply is still separately
  gated — review the 3 printed IDs yourself before running it.
- **Retry/backoff for failed extraction**: already well-designed
  (exponential backoff capped at 72h after 4+ failures, never a
  permanent write-off). Checked before considering changes — no work
  needed here.

---

## Part D — Data-dependent work (do not start yet)

### D1. 🔬 Personalization
Not data-ready: 324 events, 1 signed-in user, 5 outcome events, 2
rankings total, per Codex's own production audit. The full design exists
in `docs/doctrine/CRAVE_MASTER_PRODUCT_INTELLIGENCE_BIBLE.md` §5 and
`CRAVE_DECISION_INTELLIGENCE_ARCHITECTURE.md` §6-7. Re-check the actual
event count before starting, not this document's snapshot — but as of
now, the honest answer is "not yet."

### D2. 🔬 Ranking beyond a single score
Same gate as D1 (architecture doc §9-14).

---

## Part E — Screens / UX

### E1. Place Detail polish (closest to done)
77-79/100 against `docs/doctrine/CRAVE_PLACE_DETAIL_SPEC.md`'s §33
rubric, target 85+. Every remaining point needs real device/simulator
screenshots compared against specific rubric line items — not more code
sight-unseen.

### E2. 🔬 Craves — make it active, not a bookmark list
Doctrine §38 assumes saved places resurface at the right moment.
Research what "the right moment" means concretely before building
anything.

### E3. 🔬 Video's missing home
Feed action vs. Place Detail affordance vs. own tab — product decision,
lay out tradeoffs, don't pick unilaterally.

### E4. Map/Search "search this area" sync
Still unfinished even after the clustering fix (PR #57). Scoped and
buildable.

### E5. Empty-state / error-state audit (doctrine §42)
Most existing fixes were reactive bug fixes, not a designed pass. Audit
first, fix only confirmed gaps.

### E6. Accessibility audit (doctrine §33.I)
No dedicated pass yet. Same audit-first approach.

### E7. Onboarding / cold-start review
Compare doctrine's §18/cold-start spec against actual current behavior —
verify before assuming it's broken.

### E8. 🔬 Category taxonomy split
32 flat categories mixing cuisine/meal-period/dietary/experience/
ownership. Research what a real multi-dimension taxonomy looks like
before any migration — this touches every place row, migrate in bounded
batches like the population canary.

### E9. Search intent parsing
No typo tolerance, no "cheap tacos open late" parsing. Buildable now,
doesn't need to wait for anything.

### E10. 🔬 Group/social decision-making
Doctrine §16 — lowest priority, don't start until E2/E3 are further along.

---

## Part F — Needs the human directly (not buildable by an agent)

- Rotate `API_KEY` (burned, pasted in chat repeatedly).
- Set `DEBUG_API_KEY` in Railway (`/debug/*` routes stay 503 until then).
- App Store prep (hosted Privacy Policy URL, Apple Developer membership,
  screenshots).
- Physical-device smoke pass (a real phone, not a simulator) — Auth/
  Feed/Search/Place Detail/Save/Map/Upload/Offline/Push/Decision Session,
  plus signed push delivery to a locked device.
- Expo SDK 54→55 upgrade blast-radius report (research task, but the
  decision to actually upgrade is the human's call given real-device
  testing implications).

---

## Overall sequencing

1. **A2 (profile throughput) → A3 (fix 2 broken sources) → A1 (run the
   backlog)** — this is where most of the near-term coverage gain lives,
   and it's mostly zero-new-code.
2. **B1 (design the image holdout)** in parallel — research, not code.
3. **A4 (BentoBox adapter), E9 (search intent), E1 (Place Detail
   screenshots)** — concrete, buildable, no research gate, pick up in
   any order.
4. **E4, E5, E6, E7** — scoped audits, moderate effort.
5. **A7 (source discovery), A5 (OCR extension)** — after A1-A4 land.
6. **D1, D2 (personalization/ranking)** — only once the event-count
   gate is actually satisfied. Biggest, most consequential work in this
   whole document — do not rush into it.
7. **E2, E3, E8, E10** — product decisions and larger builds, pick up as
   capacity allows.

## Reporting back

Same as every prior handoff: exact commit SHA, exact commands + output,
known gaps stated plainly, next action named. Claude independently
re-verifies everything before any merge — including re-checking whether
a proposed "gap" is actually already solved, the way this document had
to correct itself once already.
