# CRAVE Design System

**Status:** Canonical scope artifact (2026-09-07)
**Purpose:** How the intelligence locked in
`CRAVE_EVIDENCE_SIGNAL_HIERARCHY.md` is allowed to *look*, before the
Component Registry and individual Screen Contracts freeze anything
visual. Formalizes the existing token system in
`frontend/src/constants/colors.ts` — confirmed "decent" by the earlier
screen audit — and closes its one confirmed gap (no Typography scale),
rather than inventing a disconnected system next to it.

**Authority hierarchy:** existing doctrine → reconciliation map →
annotated supersessions → V1 Scope → Target Screen Registry → Route &
Flow Map → Data & State Map → Privacy/Permission Matrix → Evidence/
Signal Hierarchy → this document. `CRAVE_MASTER_PRODUCT_INTELLIGENCE_BIBLE.md`
§30 (Screen Visual Doctrine), §31 (Banned/Anti-AI-Slop List), §32
(Originality Test), and §33 (Master Brutal Screen Rubric) remain
authoritative and are not restated in full here — this document
extends them into concrete tokens and grammar, it does not replace
them.

---

## 1. What already exists — confirmed, not reopened

`frontend/src/constants/colors.ts` today: `Colors` (background
`#0A0A0A`, surface `#1A1A1A`, surfaceElevated `#252525`, border
`#2A2A2A`, text `#FFFFFF`, textSecondary `#8C8C8C` — deliberately
tuned to clear WCAG AA 4.5:1 on all three surfaces, see the file's own
contrast-audit comment — textMuted `#555555` for disabled-only use,
semantic success/warning/error, one accent `primary` `#38BDF8`, and
four **catalog percentile tier** colors), `Spacing` (xs4/sm8/md12/
lg16/xl24/xxl32), `Radius` (sm8/md12/card14/pill20/full9999), and
`Shadows` (card/control/floating/sheet tiers, added specifically
because flat-bordered cards were reading as "flat cutouts"). **All of
this stands as-is.** Nothing in this document changes a Colors,
Spacing, Radius, or Shadows value.

**The one confirmed gap:** no `Typography` scale exists anywhere. A
direct count across the current codebase found **16 distinct
`fontSize` values in active use** (10, 11, 12, 13, 14, 15, 16, 17, 18,
19, 20, 22, 24, 26, 56, 64), heavily clustered at 12-16 with no naming
convention — the earlier audit's own finding that a "meta/caption" role
reads as 11 in one component, 12 in another, 13 in a third. §2 closes
this gap.

---

## 2. Typography scale

Eight named roles, replacing the 16 raw values. Each touched file
should migrate to the named role nearest its current intent — this is
not a mandate to touch every file that already works, but every *new*
or *edited* text style must use a named role, never a raw number.

| Role | Size | Weight | Line height | Letter spacing | Use |
|---|---|---|---|---|---|
| `micro` | 11 | 500 | 14 | 0 | Least-important metadata: timestamps, tiny counts, footnote-level text. |
| `caption` | 12 | 500 | 16 | 0 | Secondary/meta text: sublabels, helper text, tags. Consolidates the 11-13 drift cluster the audit found. |
| `body` | 14 | 400 | 20 | 0 | Default body text — the largest single cluster observed (55 of ~230 sampled instances). |
| `label` | 16 | 600 | 22 | 0 | Emphasized body: list-item titles, form labels, primary row text. |
| `subtitle` | 18 | 700 | 24 | 0 | Section headers, card titles, sheet headers. |
| `title` | 22 | 800 | 28 | -0.2 | Screen-section titles. Consolidates the 20/22 cluster. |
| `headline` | 26 | 900 | 32 | -0.3 | Major headline copy — the Spotify-Wrapped-style personality headline the audit praised on Profile ("42 places ranked. You know this city."). |
| `display` | 56 | 900 | 60 | -0.5 | Reserved for genuine hero moments only — today, exactly one: Rank's score-reveal. Not a general "big text" role; adding a second use requires the same deliberateness as adding a second hero moment to the product. |

**Migration mapping** (raw value observed → named role): 10/11 →
`micro`; 12/13 → `caption`; 14/15 → `body`; 16/17 → `label`; 18/19 →
`subtitle`; 20/22 → `title`; 24/26 → `headline`; 56/64 → `display`
(64 was drift near the same hero moment, not a second intentional
size — collapses to 56).

**Codex rule:** no new or edited text style may specify a raw
`fontSize` — only a named role from this table. A screen contract
needing a size not in this table is a signal to raise it here, not to
add a ninth raw number quietly.

---

## 3. Spacing / radius / elevation — confirmed as-is

`Spacing`, `Radius`, and `Shadows` require no new values for anything
locked so far in this project. Their assignment, formalized:

- **Radius.card (14)** is deliberately not `Radius.pill` — cards stay
  sharper/editorial, not soft-rounded-friendly, per the locked visual-
  identity answer (cinematic/intimate/editorial, never the consumer-
  social-app softness that reads as "not CRAVE," per Bible §31 item 4's
  "identical rounded cards for every concept" ban and item 5's "pill
  overload").
- **Radius.pill (20)** stays reserved for genuinely pill-shaped controls
  (toggles, the Feed context chip, filter chips) — not cards.
- **Shadows.card** is the default resting elevation for content cards
  (Feed, Discovery, Craves, Search results). **Shadows.control** is for
  persistent interactive floating controls (Map's own controls,
  toolbar-style buttons). **Shadows.floating** is for momentary
  overlays (Toast). **Shadows.sheet** is for bottom sheets (Map's
  bottom sheet, any future modal sheet). No fifth tier is needed until
  a real surface doesn't fit one of these four.
- **Spacing.xxl (32)** remains the largest named gap. "Spacious, not
  dense" (locked visual-identity answer) is achieved by *using* xl/xxl
  generously between sections, not by adding a larger token — density
  is a usage discipline, not a missing value.

---

## 4. Color usage doctrine

- **One signature accent, used sparingly.** `Colors.primary` (`#38BDF8`)
  is CRAVE's only accent color. It marks the single most important
  interactive element on a screen (a primary CTA, an active tab, a
  selected state) — never a decorative fill, never repeated across
  every icon on a screen "because it's the brand color" (Bible §31
  item 17).
- **Semantic colors (success/warning/error) are functional, not
  decorative.** Reserved for their literal meaning (a confirmed action,
  a caution state, a destructive/error state) — never repurposed as a
  fourth "brand" accent.
- **The four catalog-percentile-tier colors (`tierCravePick`/
  `tierGem`/`tierSolid`/`tierNew`) are a catalog fact, not a taste
  signal — and are the only tier-colored palette that gets its own
  hues.** Formalized rule below (§6) prevents a second colored-badge
  palette from being invented for a conceptually different tier system.
- **Dark mode is the only mode specified for V1.** No light-mode token
  set exists or is required by anything locked so far.

---

## 5. Decision Strip grammar

The exact copy/slot structure already locked across the product-design
interview and the reconciliation map, assembled here as one formal
grammar rather than scattered references:

```
[ ROLE/REASON LABEL — text only, never color-coded ]
[ Fit language: "Strong fit" — never a percentage ]
[ Practical facts: distance · price · hours-if-real-data-exists ]
```

Three entry-source variants, same slot structure, different label —
never a fabricated reason for an entry source that doesn't have one:

- From Decision Session: `BEST FIT TONIGHT` (or `SAFE BET` / `WILDCARD`)
  + the terse reason line.
- From Discovery: `WHY CRAVE SURFACED THIS` + the terse reason line.
- Organic entry (search-by-name, map tap with no recommendation
  context): practical facts only — no fit language, no fabricated
  reason (reconciliation entry #1's exact rule).

**Codex rule:** `Best Fit`/`Safe Bet`/`Wildcard` are never rendered as
three different badge colors — reconciliation entry #2 locked this
explicitly (text reasoning over color-coded badge semantics, to avoid
turning a plain-language recommendation into a decoded badge system).
Operational facts (hours/open-status) render only when real data
exists, per reconciliation entry #4 — omitted, never fabricated.

---

## 6. Tier presentation — three systems that must never be visually confused

CRAVE has three genuinely different "tier" concepts. Conflating their
visual language is one of the easiest ways for Codex to accidentally
merge concepts that the product doctrine has deliberately kept
separate.

1. **Catalog percentile tier** (CRAVE Pick / Hidden Gem / Worth Knowing
   / Explore) — a fact about the *place*, independent of any user.
   Keeps its existing four colors (already correct per the earlier
   audit: "already correctly not personalization, labeled as a catalog
   fact").
2. **Decision Session roles** (Best Fit / Safe Bet / Wildcard) — never
   color-coded (§5). Text only, always.
3. **Rank's personal tiers** (Elite / Love / Good / Not for me) — a
   fact about *this user's* taste, and must not borrow the catalog
   tier's four colors (different meaning, same hues would read as the
   same system). Treatment: text label + at most one accent moment —
   `Colors.primary` may mark the top tier (Elite) as a small, deliberate
   highlight; Love/Good stay neutral (`text`/`textSecondary`); Not for
   me stays muted, not alarm-red — it's an exclusion state, not an
   error. This avoids inventing a second four-color badge palette for a
   second tier system (Bible §31 item 5, "pill overload," and item 25,
   ratings/tiers "copied from directory products without strategic
   purpose").

**Codex rule:** never reuse the catalog-tier colors for Rank's personal
tiers or vice versa, even if a hue would "happen to fit" — the two
systems must be visually distinguishable at a glance specifically
because they answer different questions ("is this place broadly good"
vs. "do *you* like this place").

---

## 7. Cards, sheets, buttons, chips

- **Cards** — `Radius.card`, `Shadows.card` resting elevation, content-
  first imagery (photography dominant where evidence supports it, per
  the Evidence/Signal Hierarchy's dish/restaurant presentation rules) —
  never a fourth nested card-inside-card layout (Bible §31 item 13).
- **Sheets** — `Shadows.sheet`, reserved for bottom-sheet patterns
  (Map's existing hand-built drag-to-dismiss physics is the reference
  implementation — reuse it, don't reinvent a second sheet mechanic).
- **Buttons** — one primary, at most one secondary, remaining actions
  flat/text-only — the descending-weight hierarchy the audit already
  praised on Rank's done-stage (filled → outlined → text-only) is the
  *standard* for every screen with a primary action, not a Rank-
  specific pattern. A screen with three equally-loud buttons is a
  hierarchy failure, not a design preference (Bible §31 item 31,
  "duplicate controls across tabs with different semantics" — the
  fix is one consistent hierarchy pattern, reused everywhere).
- **Chips** — used for the Feed context chip, Search's editable
  constraint chips, and reason codes. Text-forward, minimal fill,
  `Radius.pill`. Never allowed to multiply into a "giant filter wall"
  (Bible §31 item 26) — a chip row that needs a second row to fit is a
  signal to redesign the density, not to keep adding chips.

---

## 8. States

Every screen needs the full state set — loading, empty, error,
offline/stale, permission-denied, partial-data, zero-result, retry —
designed explicitly, not left as "it happens to work because the
fetch hook handles it." `CRAVE_PLACE_DETAIL_SPEC.md` §8's per-state
table (initial load / partial data / no images / no menu / no friend
rankings / saved-unsaved / upload states / API error / stale-request
cancellation) is the reference rigor level — every future Screen
Contract's state section should be held to that same standard, not a
lighter one.

- **Empty states** do one of three things (Bible §42): explain why,
  offer the next useful action, or demonstrate future value. Never
  look like an unfinished screen (Bible §31 item 8, item 33).
- **Offline/stale states** show last-known content with an honest
  timestamp (Route & Flow Map F11) — never a blank screen, never a
  silently-faked-live view. Facts that are genuinely unsafe when stale
  (hours, availability) get an explicit caveat beyond the general
  staleness label.
- **Zero-result states** name the smallest specific relaxation
  (Search's already-locked pattern) rather than a generic "nothing
  found."
- **Permission-denied states** always have the manual fallback named in
  the Privacy/Permission Matrix's Permission Failure & Degraded-Mode
  Matrix — never a dead end.

---

## 9. Motion & haptics

- Subtle by default. Tactile haptic confirmation is reserved for
  genuinely major actions (a Rank comparison, a commit action, a post
  publish) — not every tap, which would cheapen the signal into
  background noise.
- Visible-but-light animation when a Decision Session slot gets
  replaced, so the user understands something changed — functional
  clarity, not decoration.
- **No parallax or immersive scroll effects, anywhere** — the hallmark
  of exactly the entertainment-optimized interaction language this
  product has been built against.
- **Tap-to-play only for video, no exception for muted autoplay** — a
  muted autoplay preview is still the scroll-triggers-motion mechanic
  that makes short-form apps addictive; muting the sound doesn't change
  that.
- **No swipe-to-decide gesture, anywhere, ever** — a durable, global
  prohibition, not a Feed-specific rule. Standard scroll gestures are
  unaffected.
- **Reduced-motion mode** strips all nonessential movement while
  preserving functionally meaningful feedback in a reduced form (a fade
  instead of a slide) — never stripping confirmation entirely.

---

## 10. Accessibility

- **Contrast:** `textSecondary` (`#8C8C8C`) is tuned to clear WCAG AA
  4.5:1 against all three surfaces — reuse it as-is for any secondary
  text; do not introduce a new gray without the same audit rigor.
  `textMuted` (`#555555`) fails AA outright and is disabled-state-only,
  always paired with `accessibilityState={{disabled:true}}`, never
  relied on for meaning via color alone.
- **Touch targets:** 44pt minimum, the value already in use in the root
  layout's own error-boundary button (`eb.btn`, `minHeight: 44`) —
  formalized here as the app-wide minimum, not a one-off.
- **Screen-reader/scalable-text/reduced-motion** support is baseline
  for every screen, not a later pass (V1 Scope §7.2) — CRAVE's
  gesture-light interaction style (no swipe-to-decide, tap-to-play
  video, terse text reasoning everywhere) should make this easier to
  achieve than a typical gesture-heavy competitor, not harder.
- **Recommendation meaning must remain understandable without
  photography or color** — a direct, free consequence of the Decision
  Strip's text-forward grammar (§5): the reasoning was never dependent
  on seeing the image or perceiving a specific color in the first
  place.
- **Map workflows** always have a list-equivalent (already locked); no
  interaction anywhere is swipe-only, so no button-alternative carve-
  out is needed beyond what §9 already guarantees.

---

## 11. Anti-slop enforcement

`CRAVE_MASTER_PRODUCT_INTELLIGENCE_BIBLE.md` §31's 37-item banned list
and §32's Originality Test govern this Design System in full — not
restated here. This document's own decisions specifically reinforce a
handful of those items: no pill-overload from tier systems (§6), no
duplicate card-inside-card layouts (§7), no unexplained recommendation
badges (§5's rule against color-coding Decision Session roles), and no
giant filter walls (§7's chip discipline). Any new component proposed
in the upcoming Component Registry gets checked against §31's full
list before being accepted, not just this document's subset.

---

## 12. Codex Design Invariants

1. No raw `fontSize` in new or edited text styles — named roles only
   (§2).
2. No new `Colors`, `Spacing`, `Radius`, or `Shadows` value without an
   approved, traceable canonical change — extend this document first,
   never add a token silently inside a screen file.
3. The three tier systems (§6) never share visual language — no
   exceptions for "it looked fine in this one case."
4. Decision Session roles are never color-coded (§5) regardless of how
   a future mockup makes the case.
5. No swipe-to-decide gesture and no muted-autoplay video, anywhere,
   under any framing (§9) — these are durable prohibitions, not style
   preferences that a screen contract can locally override.
6. A screen is not "done" if its state set (§8) is incomplete,
   regardless of how polished its happy path looks.

---

## 13. Next artifact

Per the sequence, the next canonical artifact is the **Component
Registry** — defining what becomes shared versus screen-specific
(`PlaceCard`, compact cards, ranked rows, Empty/Error states, Decision
Session cards, operational-status displays, reason blocks, Map cards,
and so on), so Codex has one registry to check before creating a fifth
version of the same primitive.
