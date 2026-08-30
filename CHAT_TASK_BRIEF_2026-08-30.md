# Task brief for Codex — 2026-08-30

Everything below is real, current, pulled straight from `CRAVE_STATUS.md`
on `main` (commit `476ad3a`) plus the live production-canary state. Not
speculative, not stale.

**Ground rules:**
- Use `.agent-bridge/` per `AGENTS.md`/`PROTOCOL.md` — claim in `STATE.md`
  before editing, write handoffs to `codex-to-claude.md`, never touch
  `claude-to-codex.md`.
- **If you're not sure the right approach, or think there's a better way
  than what's written here, say so and research it first** — read the
  relevant code/docs, check what similar decisions already made in this
  codebase, and propose the approach in your handoff before implementing.
  Don't guess, and don't silently pick the first thing that compiles.
- Every claim in a handoff must be independently verifiable — exact
  commands run, exact output, not "should work."
- Nothing that touches production data ships without the same staged/
  reversible/exact-confirmation pattern PR #61 already established.

---

## 1. Entity/existence review of the staged canary batch (do this first)

Batch `oakland-20260830-a`: 10 Oakland `DiscoveryCandidate` rows are
staged in production, all `blocked=True, resolved=False` (verified
independently — see PR #61's review thread). Nothing is public. Nothing
should become public until this review is done.

For each of the 10 rows, determine one of:
- **existing match** — this is a place already in our `places` table
  under a different name/alias → do not promote, note the alias
- **moved or closed** — current first-party/municipal evidence says so
  → leave blocked, do not promote
- **genuinely new/current** — verified currently open via a real,
  current source (not just presence in the Overture snapshot) → eligible
  for release

Your own findings in `docs/POPULATION_CANARY_2026-08-30.md` already flag
5 of the sample as "likely duplicate within 100m" and named several
specific cases (Odin/NIDO, Good Vybes & Brews, Tiger's Taproom, Oakland
United Beerworks, the stale Forge Pizza record) — finish the same
per-record rigor for all 10, not just the ones already spot-checked.

**Release rule, already written in the doc:** no more than 5
confirmed-new records at once, then verify Feed/Search/Map/Place Detail
before considering the rest. Do not batch-release all 10 just because
they pass.

## 2. Menu provider coverage is still zero

The provenance fix (image/provider/source_type lineage) is deployed, but
every existing `menu_items` row predates it — provider coverage reads as
0% because nothing's been rematerialized since. Research the safest
batching approach (how many places per pass, how to avoid re-triggering
paid extraction unnecessarily) before writing a rematerialization script
— this is exactly the kind of thing to propose, not just run.

## 3. Two placeholder menu rows still live

`is_obvious_placeholder_item()` now blocks new placeholder rows at
publish time, but two existing `MenuItem` rows named "Test"/"test" with
$0 price were already published before the guard existed. They clear
automatically the next time their place's menu gets republished — find
which two places, confirm republishing is safe (won't lose real data),
and either trigger it or document why it's better to wait.

## 4. Legacy image classification (research needed, no clear path yet)

2,530 existing place images have unknown Phase 3 content classification.
A dry-run was already tried and rejected: 90.3% came back "unknown,"
meaning whatever heuristic ran mostly encoded URL/position guesses, not
real visual signal. Don't just rerun the same dry-run — investigate why
the signal was so weak (wrong heuristic? missing real classifier? bad
sample?) before proposing a next attempt.

## 5. Expo SDK 54 → 55 upgrade

Clears a known `expo-notifications` Keychain/persisted-registration
warning (fixed upstream in `expo-notifications` 55.0.13,
expo/expo#43829). Not urgent — app runs fine today. Before touching
anything: research what else changes between SDK 54 and 55 for this
specific dependency tree (react-native-maps, expo-router, the other
native modules already in `package.json`) and report the actual blast
radius before touching a single file. This is a real upgrade, not a
patch bump — don't treat it as one.

## 6. Product decision — record-video discoverability (research, don't decide alone)

Video record has no discoverable entry point beyond a small chip on
Place Detail. Three options exist: a Feed action, a Place Detail
affordance, or its own tab. This is a product call, not a technical one
— research how each option affects the existing nav structure and
Feed/Place Detail layouts, lay out the tradeoffs, and bring options back
rather than picking one and building it.

## 7. Confirm the food-classifier model status in prod

Verify (read-only, no code change) whether the real food-classifier
model is actually installed and running in production, or silently
degrading to its fallback path. Report what you find — this is an
investigation task, not a fix, unless you find it's actually broken.

## 8. Place Detail is short of its own quality bar

Scored 77/100 confirmed (79 provisional) against
`docs/doctrine/CRAVE_PLACE_DETAIL_SPEC.md`'s §33 rubric; target is 85+.
Every remaining point needs an actual device/screenshot look (button-
border tap-discoverability, whether the de-boxed "why this fits"
headline reads right) — not more code changes without seeing it
rendered first. See `CRAVE_REMAINING_WORK.md`'s 2026-08-26 entry for the
full category breakdown before touching anything here.

---

## Not for Codex — needs the human directly

Don't attempt these; they're listed so nothing gets lost, not as tasks:

- Rotate `API_KEY` (burned, pasted in chat repeatedly)
- Set `DEBUG_API_KEY` in Railway (`/debug/*` routes are 503 until then)
- App Store prep (hosted Privacy Policy URL, Apple Developer membership,
  screenshots)
- Physical-device smoke pass (a real phone, not a simulator) across
  Auth/Feed/Search/Place Detail/Save/Map/Upload/Offline/Push/Decision
  Session, plus signed push delivery to a locked device

---

## Reporting back

Same format as every prior handoff this session: exact commit SHA, exact
commands run with output, known gaps stated plainly, next action named.
Claude independently re-verifies everything before any merge — assume
that happens every time, write handoffs accordingly.
