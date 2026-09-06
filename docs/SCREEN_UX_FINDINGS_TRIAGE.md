# Screen/UX findings triage

Every finding from `docs/SCREEN_INVENTORY_UX_DESIGN_AUDIT_2026-09-06.md`
(PR #143), sorted into one of four buckets so a certification run
doesn't spend time on cosmetic refactors while real defects wait.
Nothing here is re-derived — this is a categorization pass over
findings already made.

**Categories:**
- **RELEASE DEFECT** — a real functional/behavioral bug: silent
  failure, a misleading control, a missing state that could confuse
  or mislead a user. Fix before or shortly after the certification
  candidate, tracked like any other bucket-4 item.
- **ACCESSIBILITY** — belongs to the dedicated accessibility
  certification pass (matrix Section 7), not general polish.
- **PRE-RELEASE POLISH** — should happen before the final signed
  certification candidate is built, per the standing rule that
  certifying a binary and then changing Feed/Place Detail/etc.
  invalidates part of the evidence. Visual/consistency work with real
  but non-urgent user impact.
- **POST-LAUNCH** — code hygiene, DRY consolidation, or low-impact
  visual drift with no meaningful user-facing effect. Safe to defer
  past the first release.

## RELEASE DEFECT

1. **Rank's "retry" button doesn't actually retry** — `rank/[placeId].tsx`'s
   top-level `ErrorState`'s `onRetry` calls `router.back()`, not a real
   refetch. A user who taps "retry" after a load failure is told the
   button will retry and it doesn't — a misleading control, not just a
   missing feature.
2. **`record-video`'s failed `recordAsync()` has no user-facing error**
   — silently resets recording state with only a `__DEV__` console
   warning, the one failure path in that file that doesn't toast. A
   user who records a video that fails gets no explanation at all —
   the exact "silently fails" pattern this app's hardening phases
   otherwise eliminated everywhere else.
3. **Leaderboard has no distinct "sign in to see Friends board" state**
   — an unauthenticated user toggling to Friends likely sees the
   generic "Nobody on the board yet" empty copy instead of a sign-in
   prompt, misrepresenting "you're not signed in" as "the board is
   genuinely empty."
4. **Account deletion's visual weight is identical to Sign Out** — not
   a silent-failure bug, but a real safety gap on an irreversible,
   destructive action: nothing on the settings screen itself signals
   "this is categorically more dangerous" until after it's already
   been tapped. Worth fixing standalone given the destructive-action
   stakes, independent of the broader polish pass.

## ACCESSIBILITY

No new accessibility-specific defects came out of this audit — it
wasn't a dedicated accessibility pass (that's matrix Section 7,
**NOT STARTED**, its own runbook still to be written). One prior
finding is worth carrying forward as already-resolved context:
`constants/colors.ts`'s `textSecondary` value was already bumped
(2026-08-26) to clear WCAG AA contrast on all three surface tones,
per `ACCESSIBILITY_CONTRAST_AUDIT.md` — that fix predates this audit
and isn't a new finding, just confirmed still in place.

## PRE-RELEASE POLISH

Do these before the final signed certification candidate is built,
per the standing rule that a later Feed/Place Detail/etc. change
invalidates part of a candidate's certification evidence.

1. **No shared `Typography` scale** — the single biggest lever;
   screens hand-type 7-14+ distinct font sizes each with no naming
   convention.
2. **`Shadows` token defined but only ~3 of 13 components use it** —
   most cards (including Place Detail's) render flat/unelevated.
3. **Two parallel ranked-row implementations** — Leaderboard
   reinvents its own row instead of reusing `RankedPlaceRow`, the
   cheapest visual-consistency win in the whole audit.
4. **Place Detail lacks in-page hub navigation** — no section
   chips/tabs, a single linear scroll — the highest-leverage
   structural gap on the screen meant to be the app's visual center.
5. **Place Detail's video-gallery empty state is unlabeled** (a flat
   color box, no icon/text) versus `ImageGallery`'s real "No photos
   yet" state on the same screen — an inconsistent, under-communicated
   empty state next to a well-designed one.
6. **Rank's initial place-fetch loading is a bare spinner**, not the
   skeleton pattern every other list-adjacent screen uses.
7. **Rank's sign-in gate hand-rolls a near-duplicate of `EmptyState`**
   instead of reusing it.
8. **Onboarding (`profile-setup.tsx`) has no illustration/moment** —
   the first screen a new user completes after sign-up, currently a
   bare two-field form.
9. **Craves' remove-a-save has no confirmation** — likely fine given
   it's reversible, but worth a deliberate decision either way rather
   than an unreviewed default.

## POST-LAUNCH

Safe to defer — code hygiene or low-impact visual drift, no
meaningful user-facing effect.

1. **`PlaceCard`/`PlaceCardCompact` duplicate derivation logic** across
   two separately hand-typed style sheets with drifted values for the
   same visual role — a real DRY issue, not a user-visible one.
2. **Map's error/empty banners don't reuse `EmptyState`/`ErrorState`**
   — its own hand-rolled banners work correctly; this is a consistency/
   maintainability question, not a functional gap.
3. **`add-spot.tsx` hand-rolls its own empty/error text** instead of
   the shared components — same category as above.
4. **`Radius` token drift** — literal `22` in `add-spot.tsx`/
   `+not-found.tsx` where `Radius.pill` (20) exists; `PlaceCardCompact`'s
   `chip` uses a literal `10` matching no token.
5. **Root `_layout.tsx` hardcodes `'#FFFFFF'`** for `headerTintColor`
   instead of `Colors.text`, in the same file that otherwise threads
   tokens everywhere.
6. **Tab bar's active-state treatment is icon-swap + color only** — no
   pill/background highlight. A nice-to-have for chrome-level identity,
   not urgent.
7. **Settings and the legal pages are structurally generic** — both
   function correctly and their content is accurate; the genericness
   is a personality gap, not a defect, and lowest-priority relative to
   Feed/Place Detail/Map/Craves/Rankings.
8. **+not-found is minimal but functional** — already an intentional,
   on-brand recovery screen, just not visually elaborate.

## How this feeds certification

Certification (matrix Section 10) should track the 4 **RELEASE
DEFECT** items as narrow bugfix PRs through the normal CI/CodeRabbit
gate — same discipline as any other certification failure (matrix
Section 12). The **PRE-RELEASE POLISH** list is the actual scope of
the screen-by-screen pass before the certification candidate is
built, in the priority order the audit already established: Feed →
Place Detail → Map → Craves/Rankings → Profile/Settings → edge-state
screens. **POST-LAUNCH** items should not block anything — track them
in this doc, revisit after the first release ships.
