# CRAVE Frontend Execution Order

Status: **LOCKED** — this document is the authoritative execution order for
all frontend work going forward. It supersedes the old wave-numbered
sequencing (`CRAVE_IMPLEMENTATION_MIGRATION_PLAN.md`'s Waves 5-10) for
**frontend** work specifically. Backend/production-data lanes (OSM backfill,
menu backlog canary, population-coverage canaries, etc.) are separate and
unaffected — see `.agent-bridge/STATE.md` and `.agent-bridge/claude-to-codex.md`
for those.

Waves 0-7 (navigation topology, Feed/Decision Session, Search Screen Contract,
Craves intelligence, Place Detail relationship hierarchy) remain merged
baseline and are not reopened by this document. This document controls what
happens **next**.

## Why this exists

A full frontend audit (2026-09-10/11, verified line-by-line against current
`main` — see "Grounding findings" below) found the codebase is
architecturally strong (~85% mature: Search, contextual Map, Craves, Rank,
Place Detail foundations, offline queues, posting-draft persistence,
recommendation instrumentation, route-level race protection, five-tab
topology) but has a specific, real cluster of problems: a Profile/social
stack still built around the older leaderboard/follower-count concept, three
concrete release blockers (Activity placeholder, `crave://`-only sharing,
"Rate CRAVE — Coming soon"), and — most importantly for *how* work should
proceed — a set of cross-cutting concerns (auth-gate behavior, error
handling, remote-state ownership, recommendation telemetry) that different
screens have each solved slightly differently, rather than once, correctly,
in one place.

The first instinct — "fix every shared system before touching a screen" —
was rejected as too risky: it produces a long phase with no visible,
demoable progress and a real chance of designing abstractions speculatively,
before any real screen has exercised them. **Vertical-slice migration** is
the adopted alternative: lock the minimum shared contracts, prove them on
one real screen, extract only what's proven, then propagate slice by slice.

## The locked order

```
Foundation Gate
  → Place Detail (proving slice)
  → Feed / Decision Session (journey)
  → Search / Map (propagation-only slice — see boundary below)
  → Craves
  → Rank
  → Food Evidence / Add Spot
  → Profile / Taste / social cleanup
  → Auth / Settings / Activity completion
  → cross-app accessibility / E2E / release certification
```

Each slice: **design → implementation-audit → fix → test → device-verify →
lock**, same discipline already used for Search/Craves/Place Detail's own
certification passes. No slice is "done" on code alone — it needs the same
verification rigor (`tsc --noEmit`, full test suite, CodeQL, and for a UI
change, an actual running-app check) already standard in this repo.

### 1. Foundation Gate

Lock the **minimum** shared contracts — interfaces and invariants, not every
future implementation:

- `PendingIntent` / auth-gate contract (below).
- Server-state ownership rule: Zustand owns client/local/draft/workflow
  state; TanStack Query owns remote server state (see rule below).
- Error taxonomy (below).
- Recommendation-event envelope (extensible schema, real fields only —
  see rule below).
- Deep-link destination contract (universal-link shape, cold/warm/signed-out
  behavior — see `crave://` finding below).
- Privacy/provenance scopes: private / shareable / display-identity /
  explicit-opt-in, and value/source/fetched_at/confidence provenance for
  place data (hours, menu, images).

This is a contracts-and-invariants pass, not a "build every shared module"
pass. Don't implement a piece of shared infrastructure until a real screen
needs it.

### 2. Place Detail — proving slice

Place Detail is the proving ground because it already touches every
cross-cutting concern above: auth, remote state, Save, recommendation
context, image/menu provenance, sharing/deep links, errors, offline
behavior, analytics. Build/fix it against the Foundation Gate contracts
directly (not against a shared module yet).

Also lands here, since they're Place Detail-scoped:
- Contextual primary action (one moment-specific CTA, not six equal ones —
  never-visited → Save; likely-there-now → "I'm here"; visited-not-ranked →
  Rank; saved-and-nearby → Directions; recommendation session → Choose this).
- "Report an issue" as a first-class, structured-signal correction path
  (`closed` / `wrong_hours` / `wrong_menu` / `wrong_photo` / `wrong_location`
  / `duplicate` / `other`), not just free text.
- Provenance-aware copy: "Open until 10 PM" only when the underlying claim
  actually supports that confidence; "Hours may have changed" otherwise.

### 3. Extraction

Once Place Detail proves the pattern, move the reusable pieces (auth-gate
hook, error-taxonomy mapper, query-key factory, provenance renderer) into
shared modules. Do not design these modules speculatively ahead of a screen
that needs them.

### 4. Propagate by journey

`Feed → Place → outcome`, `Search → Map → Place`, `Craves → Place`,
`Rank → completion`, `Food Evidence → Place`. Each slice ships a visibly
better screen while simultaneously migrating the underlying architecture —
not "infrastructure now, screens later."

### 5. Finish cross-cutting last

Remaining manual-fetch routes, the full `catch` classification pass,
accessibility certification, telemetry consistency, and the full E2E journey
matrix are finished once the journeys above have propagated the pattern
everywhere it needs to go — see the E2E rule below for why this can't be
front-loaded either (it needs real screens to test).

## Scope boundary — Search/Map (read before touching either screen)

> Search/Map vertical-slice work may propagate shared frontend contracts,
> reliability improvements, data-state conventions, auth/error/query
> ownership, accessibility fixes, and integration hardening **only**. It
> must not redesign or reopen the certified Search Screen Contract or
> approved Search/Map UX unless a new, proven contract gap is documented
> first.

Wave 5's Search Screen Contract (PRs #190-193) and the Search/Map V1.5
design-audit fixes (PRs #225/#226/#229) are certified and merged. This
slice is architecture propagation into an already-approved screen, not a
reason to redesign it. If a genuine new contract gap is found while
propagating, document it (same process as every prior Search gap: named,
verified against the actual contract text, fixed as its own scoped PR) —
don't silently redesign around it.

## Locked rules

### React Query migration rule

Migrate a route to TanStack Query **opportunistically**, when that route is
already being audited/finalized as part of a slice above — not as a
standalone mechanical migration across all routes. (Current state, verified
2026-09-11: only 4 of ~30 routes use `useQuery`/`useMutation` —
`place/[id]`, `rank-home`, `friends-feed`, `leaderboard`. Everything else is
manual `useState`+`useEffect` fetching.)

Lock these conventions **early** (at the Foundation Gate, before the first
opportunistic migration) so every subsequent migration follows the same
pattern instead of reinventing it per-route:
- query-key factory shape (so cache invalidation and account-isolation are
  structural, not per-screen judgment calls)
- cancellation behavior
- stale-time defaults
- account-isolation on account switch (mirrors `authStore.signOut()`'s
  existing `queryClient.clear()` + per-key `userId` scoping discipline)
- error-semantics mapping (ties into the error taxonomy below)

### Error-swallow classification rule

Never blanket-ban `catch {}` / `.catch(() => [])` / `.catch(() => {})`.
(Current state, verified 2026-09-11: 11 occurrences across 6 files —
`videoQueueStore.ts`, `cravesStore.ts`, `postingDraftStore.ts`,
`PlaceCard.tsx`, `useLocation.ts`, `usePushNotifications.ts`.) Classify each
occurrence individually as one of:

1. **Ignorable cleanup** — e.g. `FileSystem.deleteAsync(uri, { idempotent:
   true }).catch(() => {})` on an already-idempotent operation. Legitimately
   silent; may still emit telemetry.
2. **Recoverable background failure** — retry + telemetry, no user-facing
   error (e.g. a background sync pass that'll run again next foreground).
3. **User-actionable failure** — must surface to the user. A data fetch
   that silently returns `[]` on failure (indistinguishable from "genuinely
   empty") belongs here, not category 1.
4. **Invariant/programmer failure** — telemetry + dev warning; something
   that should be structurally impossible.

### Recommendation-event schema rule

`RecommendationEvent`'s own docstring already states the discipline this
repo has been following: no `algorithm_version`, `candidate_set`,
`component_scores`, `penalties`, or `reason_codes` exist yet, because there
is no ranking model to produce them. **Keep it that way.** Define an
extensible event envelope now (recommendation_id, session_id, place_id,
surface, position, and room for future fields); log only facts that
currently exist; add model-specific fields only when a real ranking model
genuinely produces them. Do not fabricate `model_version` or `reason_codes`
ahead of a model that would make them true — same truth-over-appearance
discipline as the OSM hours backfill (real OSM data only, no guessed
status) and Search's constraint-interpretation engine.

### Universal-link rule

Keep `crave://place/{id}` as an internal/fallback deep link, but make
`https://crave.app/place/{id}` (or equivalent) the primary sharing
mechanism once the Foundation Gate's deep-link contract lands. Required
behavior: app installed → opens exact place; app missing → useful web
fallback; signed-out + gated destination → auth gate preserves intent via
`PendingIntent`, then resumes; malformed/old link → controlled fallback.
Needs cold-start, warm-start, backgrounded, and terminated-state coverage
(see E2E rule) — this is a release blocker, not a nice-to-have.

### E2E rule

`frontend/e2e/` currently contains exactly one file, `smoke.spec.ts`
(verified 2026-09-11). The unit of coverage is the **journey**, not the
screen — a release-ready matrix includes at minimum: signed-out → search →
place → save → auth → resume; Google/Apple/email auth; session restore
after kill; account switch; recommendation → place → outcome; save →
Craves → remove; rank → comparisons → Rank Home; offline mutation →
reconnect → sync; capture → identify restaurant → post; Add Spot existing
vs. candidate-promotion; universal link cold-start and signed-out-then-auth;
notification → destination; location denied/permanently-blocked; backend
timeout; stale-cache/offline display; missing image/menu; VoiceOver; large
text; Reduced Motion. Build this incrementally as each journey's slice
lands above, not as one final P3 sprint — a slice isn't locked until its
own journey has real E2E coverage, not just unit tests.

## Definition of Done (per slice)

A slice is not complete until:

- [ ] Screen's purpose, hierarchy, states, interactions, data contract,
      accessibility contract, and visual contract were locked *before*
      implementation (per the existing screen-contract workflow) — Codex
      implements an approved contract, it does not redesign independently.
- [ ] `npx tsc --noEmit` clean.
- [ ] Full frontend test suite green.
- [ ] Backend `python -m compileall app` + `import app.main` clean, full
      `pytest` suite green (if backend touched).
- [ ] CodeQL/Analyze jobs green.
- [ ] New/changed remote-data screens support all five states: loading,
      success, empty, error, stale/offline — not just loading/data.
- [ ] New/changed error paths are classified per the error-swallow rule
      above, not left as an unclassified `catch {}`.
- [ ] Accessibility: labeled role/state, logical focus order, Dynamic Type
      resilience, sufficient contrast, Reduced Motion behavior, 44×44
      minimum touch targets.
- [ ] The journey(s) this slice completes have real E2E coverage, not just
      component-level tests.
- [ ] Any doctrine/contract text this slice's own findings contradict gets
      corrected in the same PR (see this repo's standing practice: name the
      gap precisely, don't silently ship over it).

## Grounding findings (verified against `main`, 2026-09-10/11)

Every item below was independently re-verified against the actual running
code by Claude, not taken on the audit's word alone — file/line references
in the original audit thread, summarized here for traceability:

- Activity (`app/activity.tsx`) is a pure placeholder (icon + static text,
  no data, no functionality) despite every tab exposing an Activity entry
  point.
- `Settings` → `label="Rate CRAVE"`, `sublabel="Coming soon"` still present.
- `AuthSheet`'s Terms/Privacy Policy are plain styled `<Text>` with no
  `onPress` — look like links, navigate nowhere.
- `crave://place/{id}` confirmed as the only share mechanism; the code's
  own comment says no `associatedDomains`/`intentFilters` exist, so it's
  native-app-only today.
- `profile-setup.tsx`'s subtitle literally reads "how you show up on
  leaderboards."
- `(tabs)/profile.tsx` renders follower/following `StatTile`s and a
  dedicated Leaderboard link prominently.
- `leaderboard.tsx`'s own top-of-file comment: "Ranked by how many places
  you've logged, not by average score... logging breadth is the behaviour
  worth rewarding," plus 🥇🥈🥉 medal framing.
- `taste-profile/[userId].tsx` renders `Top {100 - percentile}%` and a
  `{match_score}% taste match` — competitive percentile + taste-match score.
- `user/[id].tsx` renders each ranked place with `rank_score`/`tier`.
- `rank/[placeId].tsx`'s signed-out state is a static "Sign in to rank
  places" message with no `AuthSheet`/resume trigger at all — unlike the
  rest of the app's `AuthGateHost` pattern.
- Rank's "See my list" is `router.push('/profile')`, not Rank Home.
- `frontend/e2e/` contains exactly one file, `smoke.spec.ts`.
- Session persistence: `lib/supabase.ts` uses `AsyncStorage`, not
  `expo-secure-store`.
- `useQuery`/`useMutation` appear in 4 of ~30 route files.
- 11 `catch {}` / `.catch(() => [])` / `.catch(() => {})` occurrences across
  6 files.
- `RecommendationEvent`'s own docstring confirms no `reason_codes`/
  `model_version`/`component_scores` exist yet — by design, not omission.

## Next action

Claim **Foundation Gate** in `.agent-bridge/STATE.md` before starting it —
owner, branch, base SHA, allowed files, verification plan — per
`.agent-bridge/PROTOCOL.md`. Do not start Place Detail work before
Foundation Gate's contracts are committed; do not start Search/Map
propagation work without re-reading the scope boundary above first.
