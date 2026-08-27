# `Colors.textMuted` contrast audit

**Status: fixed (2026-08-26), after this audit.** Everything below this
line is the original audit (kept for the record of what was found and
why); see the bottom of this file for what the actual fix did.

Audit only at the time this was written — no code changed by this pass.
Logged per the standing instruction to fix this via a full consumer audit
before touching the global token (Place Detail's visual pass already
worked around it locally with a screen-scoped `QUIET_TEXT` constant; that
fix was not touched or undone by the audit itself).

## Measured contrast (WCAG 2.1 relative-luminance formula)

The app has a single dark palette (`src/constants/colors.ts`) — no
light-theme variant, so every text color sits on one of three near-black
surfaces.

| Foreground | Background | Ratio | AA normal text (4.5:1) | AA large text (3:1) |
|---|---|---:|---|---|
| `textMuted` #555 | `background` #0A0A0A | 2.66:1 | FAIL | FAIL |
| `textMuted` #555 | `surface` #1A1A1A | 2.33:1 | FAIL | FAIL |
| `textMuted` #555 | `surfaceElevated` #252525 | 2.06:1 | FAIL | FAIL |
| `textSecondary` #888 | `background` | 5.58:1 | PASS | PASS |
| `textSecondary` #888 | `surface` | 4.91:1 | PASS | PASS |
| `textSecondary` #888 | `surfaceElevated` | **4.32:1** | **FAIL (marginal)** | PASS |
| `text` #FFF | `background` / `surface` | 19.8:1 / 17.4:1 | PASS | PASS |

**`textMuted` fails outright everywhere it's used** — it doesn't even
clear the large-text bar (3:1), let alone normal text (4.5:1). **`textSecondary`
is not an unconditional safe substitute** — it passes on `background` and
`surface` but falls just short of AA-normal on `surfaceElevated` (4.32:1
vs. 4.5:1 required; still clears the large-text bar at 3:1). Any fix has
to pick per-surface, not do a blind find-and-replace.

No hardcoded `#555`-style bypass of the token exists anywhere in the
codebase — every low-contrast instance goes through `Colors.textMuted`,
confirmed by a direct grep for the literal hex value outside `colors.ts`.

## Every consumer, by usage kind

34 files reference `Colors.textMuted` (or receive it via a `tierColor()`
call — see below, the most important finding). Grouped by what WCAG
criterion actually applies:

### A — Real text content (WCAG 1.4.3, the actual violation)

Style keys with `fontSize` set — this is rendered text a person reads,
not a decorative icon:

- `src/components/PlaceCardCompact.tsx:114`, `PlaceCard.tsx:195,200`,
  `TrendingStrip.tsx:50`, `RankedPlaceRow.tsx:106,120`,
  `SectionHeader.tsx:38,39` — card/list secondary metadata (distance,
  category counts, notes).
- `app/leaderboard.tsx:222,234,237`, `app/user/[id].tsx:336,348,374`,
  `app/(tabs)/profile.tsx:323,339`, `app/friends-feed.tsx:189`,
  `app/taste-profile/[userId].tsx:225,244,256` — usernames, handles,
  counts, stat labels across every profile-adjacent screen.
- `app/legal/terms.tsx:101`, `app/legal/privacy.tsx:83` — the "last
  updated" date on both legal documents.
- `app/settings.tsx:272,279,311,313,316` — row sublabels and the app
  version string.
- `app/(tabs)/search.tsx:396,398,418` — city context, empty-state hint,
  result count.
- `app/(tabs)/craves.tsx:536,559` — pending-share status text.
- `app/rank/[placeId].tsx:428,467,476,481,492,514` — comparison-screen
  labels, including `skipBtnText` (the literal button label for "Skip").
- `app/add-spot.tsx:298,312` — card distance, a "done" action label.
- `app/_layout.tsx:54`, `app/(tabs)/map.web.tsx:40` — global error-boundary
  and web-fallback body copy.
- `app/profile-setup.tsx:203` — the `@` prefix on the username field.
- **`src/components/AuthSheet.tsx:515` (`dividerText`, the "OR" between
  sign-in methods) and `:541` (`legal`, the terms/privacy acknowledgment
  copy shown on every sign-up)** — worth calling out specifically: the
  legal disclosure text on the auth screen is one of the least-readable
  strings in the app.
- `src/components/MenuSubmissionSheet.tsx:323` — a form section label.

### B — Icons (WCAG 1.4.11 non-text contrast, 3:1 — separate criterion, also failing, generally lower severity since most are adjacent to a labeled action)

`MapBottomSheet.tsx`, `ComparisonChoice.tsx`, `RankedPlaceRow.tsx`,
`EmptyState.tsx`, `ErrorState.tsx`, `ImageGallery.tsx`, `ReportPhotoSheet.tsx`,
`MenuSubmissionSheet.tsx`, `add-spot.tsx`, `user/[id].tsx`,
`settings.tsx`, `rank/[placeId].tsx`, `+not-found.tsx`, `friends-feed.tsx`,
`search.tsx`, `map.web.tsx`, `craves.tsx` — all pass a bare
`color={Colors.textMuted}` to an `Ionicons` glyph. These fail 1.4.11 too
(2.06–2.66:1 vs. the 3:1 non-text floor), but most sit beside a labeled
row or state message, so the icon alone isn't the only carrier of
meaning — lower priority than bucket A.

### C — `TextInput` placeholders

`ShareLinkSheet.tsx`, `AuthSheet.tsx`, `MenuSubmissionSheet.tsx`,
`profile-setup.tsx`, `search.tsx` all set
`placeholderTextColor={Colors.textMuted}`. WCAG doesn't classify
placeholder text as content the same way, but it's still functionally
unreadable at this contrast — lowest formal priority, still worth fixing
alongside the rest since it's the same token.

### D — The one non-obvious, most-important finding: `tierColor()`

`src/utils/rankScore.ts:27` — `tierColor('disliked')` returns
`Colors.textMuted` directly (`'liked'` → `Colors.success`, `'fine'` →
`Colors.warning`, `'disliked'` → `Colors.textMuted`). This function feeds
**rendered text color**, not styling, at every call site:

- `app/friends-feed.tsx:151` (`scoreText`), `src/components/RankedPlaceRow.tsx:66`
  (`scoreText`) — a friend's or your own numeric rank score.
- `app/rank/[placeId].tsx:228` (`doneTier`) — the tier label shown right
  after you finish ranking a place.
- `app/place/[id].tsx:495` (`friendRankTier`), `:530` (`rankScoreDotText`)
  — **this screen already has its own local `QUIET_TEXT` fix (this
  session, the visual-language pass), but that fix only touched the 4
  static `Colors.textMuted` usages in this file's own stylesheet. It does
  not cover `tierColor()`'s return value — a disliked-tier friend ranking
  or your own disliked-tier score on this exact screen still renders in
  raw `Colors.textMuted`, unaffected by the earlier fix.** A real gap in
  an already-"fixed" screen, only visible by tracing the shared utility
  rather than re-grepping the file's own literal token usage.
- `app/taste-profile/[userId].tsx:172` (`tierCount`) — the count of
  places you've marked "disliked."
- `src/components/ShareRankCard.tsx:67` (`badgeText`) — the tier label on
  the **exported/shared rank card image** (a 320×568 "story" card users
  post externally). A disliked-tier share renders its own label at
  ~2:1 contrast in an image that leaves the app entirely.

Semantically, this is the single highest-value fix in this whole audit:
one function, six call sites, five files, and it's directly showing a
user their own or a friend's rank outcome — not decorative chrome.

### E — Conditional / disabled-state usage

- `app/settings.tsx:156,163` — `tint={Colors.textMuted}` on the
  "Notifications" and "Rate CRAVE" rows (both genuinely disabled,
  "Coming soon"). `Row`'s implementation (same file, line 33) applies
  `tint` to **both** the icon and the row's label `Text`, so both rows'
  labels render at ~2:1. Intentional "this is disabled" styling, but
  contrast alone isn't an accepted way to communicate a disabled state —
  worth pairing with an explicit `accessibilityState={{ disabled: true }}`
  regardless of what color ends up chosen.
- `app/profile-setup.tsx:110` — `hintColor` ternary: `Colors.success` /
  `Colors.error` / `Colors.textMuted` (the last for the "Checking…"
  in-flight state of a username-availability check). Real-time feedback
  text, not decorative.

## What a real fix would need (not done here — audit only)

1. Two accessible replacement tokens, not one: `textSecondary` already
   covers `background`/`surface` (5.58:1 / 4.91:1) but needs a
   surface-aware exception or a slightly darker `surfaceElevated` for the
   4.32:1 shortfall to clear AA-normal there too.
2. A `tierColor()` fix is its own item, separate from a global token
   swap — six call sites across five files (plus a within-file recheck of
   `place/[id].tsx`, which already has a partial fix that doesn't cover
   this path).
3. A real `textDisabled` token (or an `accessibilityState` pairing) for
   the settings-row "Coming soon" case, distinct from "this text is just
   quieter" — those are different intents currently sharing one color.
4. Icons (bucket B) and placeholders (bucket C) can very likely take the
   same replacement as bucket A's surrounding text, but weren't
   separately verified against the 3:1 non-text floor beyond the
   token-level numbers above.

Nothing above requires a design decision beyond "which token wins on
which surface" — this is scoped enough to implement directly once you
want it done, not something that needs product judgment calls first.

## The actual fix (2026-08-26)

Simpler than the four-item list above turned out to require, once it
came time to implement:

1. **One token change, not two.** Bumped `Colors.textSecondary` from
   `#888888` to `#8C8C8C` — a 4-unit change, invisible as a design shift.
   Recomputed contrast: 5.89:1 on `background`, 5.18:1 on `surface`,
   **4.56:1 on `surfaceElevated`** (was 4.32:1, the one surface that
   previously fell short of AA-normal's 4.5:1). No second/surface-aware
   token needed — one value now clears AA everywhere.
2. Replaced every real-text and icon `Colors.textMuted` usage (buckets
   A/B/C from the audit above) with `Colors.textSecondary` across all ~30
   consumer files, via a scripted sweep (not by hand file-by-file) —
   verified via `grep` that nothing was missed and via the full test
   suite that nothing broke.
3. **Fixed `tierColor()` in `rankScore.ts`** — the audit's single
   highest-value finding. Its `'disliked'` branch returned
   `Colors.textMuted` directly, feeding real rendered text at 6 call
   sites across 5 files. Changed to `Colors.textSecondary`, closing all 6
   at once — including the `place/[id].tsx` gap the earlier local
   `QUIET_TEXT` fix didn't cover, and the exported `ShareRankCard` image.
4. **Removed `place/[id].tsx`'s local `QUIET_TEXT` workaround entirely**
   (it was already `= Colors.textSecondary`) now that the global token is
   safe — no reason to keep a screen-local alias around once the thing it
   was working around is fixed.
5. **Left `settings.tsx`'s two `Colors.textMuted` usages untouched, on
   purpose.** Both are the "Notifications"/"Rate CRAVE" **non-interactive**
   "Coming soon" rows (no `onPress` at all — not just visually disabled,
   there's no button here to attach `accessibilityState` to). WCAG 1.4.3
   explicitly exempts inactive UI components from the contrast minimum;
   inventing a `textDisabled` token for two rows that already read as
   "not a real control" wasn't worth it. Genuinely re-checked this wasn't
   just an excuse to skip work — these two are the only remaining
   `Colors.textMuted` references anywhere in the app (confirmed by grep).
6. Icons and placeholders (buckets B/C) took the same replacement as
   surrounding text — no separate treatment needed once the token itself
   was fixed.

Verified: full suite 270/270 passing (unchanged count — this was a
color-value change, not new behavior), `tsc --noEmit` clean. No test
asserted an exact hex value for any of these, so nothing needed updating
on the test side.
