# Screenshot capture plan

A plan for what to capture once screens are finalized — not the
screenshots themselves. Per the standing rule that visual polish
(`docs/SCREEN_UX_FINDINGS_TRIAGE.md`'s PRE-RELEASE POLISH list) happens
*before* the certification candidate is built, do not capture final
screenshots until that polish pass is done — a screenshot of a
pre-polish screen would need to be retaken anyway.

## Required screens (priority order matches the UX audit's own ranking)

1. **Feed** — showing the tiered sections (Crave Pick/Gem/Solid/New)
   with real, appealing food photography. This is very likely the
   first screenshot a store listing shows — it needs to look populated
   and appetizing, not sparse.
2. **Place Detail** — the screen positioned as the app's visual center;
   show the rank CTA, photos, and menu section populated.
3. **Rank (comparison flow)** — the head-to-head `ComparisonChoice`
   duel screen, and/or the score-reveal moment (the 56pt score display)
   — this is the app's single most distinctive mechanic and should be
   represented, not just the list screens.
4. **Map** — with real clustered markers over a real city, not an
   empty region.
5. **Craves** — showing a populated three-source list (saves + social
   + added).
6. **Profile** — showing a populated ranked list and the
   Wrapped-style headline copy.

## Device sizes required

- **iOS**: App Store Connect requires screenshots per device size
  class currently in the submission form (6.7"/6.5" and 5.5" have
  historically been required tiers, plus iPad if the app supports
  tablets — `app.json`'s `ios.supportsTablet: true` means iPad
  screenshots are likely required; confirm the exact current
  requirement at submission time rather than trusting this list, since
  Apple's required size set changes across OS/device generations).
- **Android**: Play Console requires phone screenshots (minimum 2,
  recommended more) at a minimum resolution; 7" and 10" tablet
  screenshots are optional unless the listing targets tablets.

## Ordering

Store listings are read top-to-bottom before a tap/scroll — Feed
should be first (broadest appeal, most visually rich), Rank second
(the differentiator), Place Detail third, then Map/Craves/Profile.

## Captions (draft, one line per screenshot)

1. Feed — "Real rankings, not star averages."
2. Rank — "Compare places head-to-head. See exactly where they land."
3. Place Detail — "Everything about a place — menu, photos, your
   ranking, friends' picks."
4. Map — "See what's around you, ranked."
5. Craves — "Save it, remember it, revisit it."
6. Profile — "Your taste, in one list."

*(Final wording should be reviewed alongside the actual store
description copy in `docs/STORE_METADATA_DRAFT.md` for tone
consistency, not finalized independently.)*

## Seeded data / account state for capture

Use the "established account" from
`docs/RELEASE_TEST_ACCOUNTS_AND_FIXTURES.md` — captures need populated,
realistic-looking data (multiple ranked places across tiers, real food
photography, a followed friend or two), not a fresh empty account. Do
not use real other users' data/photos in marketing screenshots without
consent — seed dedicated test-account content specifically for capture
if the established account's real content isn't suitable to publish
publicly.

## Mechanical capture process (once screens are finalized)

1. Confirm the visual-polish pass (triage doc's PRE-RELEASE POLISH
   list) is done and merged.
2. Build a release/preview build with the seeded established account
   signed in.
3. Capture each required screen at each required device size (iOS
   Simulator / Android Emulator at the exact required resolutions is
   usually more reliable than a physical device for pixel-perfect
   dimensions, though the certification builds themselves must still
   be tested on real hardware separately per
   `docs/RUNBOOK_PHYSICAL_DEVICE_CERTIFICATION.md`).
4. Add captions (device-frame + text overlay, if that's the chosen
   store-listing style) using the draft captions above as a starting
   point.
5. Upload to App Store Connect / Play Console in the priority order
   above.
