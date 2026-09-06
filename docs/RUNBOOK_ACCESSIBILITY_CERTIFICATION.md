# Accessibility certification runbook

Permanent runbook. Run against the signed release candidate, with
VoiceOver (iOS) and TalkBack (Android) actually enabled — not a static
code read. `docs/SCREEN_UX_FINDINGS_TRIAGE.md` confirmed this audit
found no *new* accessibility defects because it wasn't a dedicated
accessibility pass; this is that pass.

## Prerequisites

- Physical iPhone with VoiceOver enabled (Settings → Accessibility →
  VoiceOver), physical Android device with TalkBack enabled.
- The signed release candidate installed (same build as physical-
  device certification).

## Screens to cover (priority order matches the UX audit's own ranking)

Feed → Place Detail → Rank → Craves → Map → Profile/Settings →
record-video → Search → Leaderboard.

## Per-screen checklist

For each screen above, with the screen reader on:

1. **Labels**: every interactive element (button, card, icon-only
   control) announces something meaningful, not "button" or a raw
   icon name. Specifically re-check `PlaceCard`/`PlaceCardCompact`'s
   accessibility label formula (`` `${name}, ${category}, ${tier}` ``,
   confirmed in the shared-component audit) actually reads naturally
   aloud, not just that it's present in source.
2. **Focus order**: swiping through the screen visits elements in a
   logical order (top-to-bottom, matching visual layout) — flag any
   screen where focus jumps unexpectedly (common failure mode: absolute-
   positioned overlays, like `MapBottomSheet` or `record-video`'s
   floating controls).
3. **State announcements**: loading/error/empty states are actually
   announced when they appear, not just visually rendered — a screen
   reader user needs to be told a state changed, not have to poll it.
4. **Destructive actions**: account deletion's two-step confirmation
   (`settings.tsx`) is fully operable and clearly announced with
   VoiceOver/TalkBack, given the triage doc's separate finding that its
   *visual* weight is under-communicated — confirm it isn't also
   under-communicated for a screen-reader user.
5. **Permission dialogs**: OS-native permission prompts are handled by
   the OS's own accessibility support (not this app's concern), but
   this app's own pre-prompt/blocked-permission screens
   (camera/mic/location) must be — re-check `record-video.tsx` and
   `add-spot.tsx`'s permission-state screens specifically.

## Dynamic Type / large text

- iOS: Settings → Accessibility → Display & Text Size → Larger Text,
  set to a large-but-realistic value (not the most extreme setting,
  which no real user profile targets, but a clearly-larger one).
- Android: Settings → Accessibility → Font size, similarly.
- Confirm no critical text or control is clipped, truncated
  illegibly, or pushed off-screen on Feed, Place Detail, Rank
  (specifically the 56pt score-reveal — the single largest fixed text
  size found in the whole app, worth checking it still fits), Craves,
  and Settings.

## Touch targets

- Cross-check `profile-setup.tsx`'s explicit `44×44` minimum
  (documented in its own code comment as a deliberate touch-target
  convention) is actually met on-device, and spot-check other icon-only
  controls (Craves' remove-save ×, Place Detail's action row) meet the
  same 44×44 minimum.

## Contrast

- Spot-check `textSecondary` (`#8C8C8C`) and `textMuted` (`#555555`,
  intentionally sub-AA, disabled-only per `constants/colors.ts`'s own
  comment) render as expected against all three surface tones
  (`background`/`surface`/`surfaceElevated`) on a real display, not
  just the math in `ACCESSIBILITY_CONTRAST_AUDIT.md`.
- Confirm `textMuted`'s two legitimate uses (Settings' disabled "Coming
  soon" rows) are actually paired with a disabled/inactive
  `accessibilityState`, not relying on color alone, on-device.

## Reduced motion

- iOS: Settings → Accessibility → Motion → Reduce Motion. Android:
  Settings → Accessibility → Remove animations.
- Confirm the app's real motion (Rank's haptics/scale-down/fade
  transitions, `MapBottomSheet`'s drag-spring physics, Feed's
  `SkeletonCard` shimmer) either respects the platform preference or
  is subtle enough not to be a real vestibular concern — this app was
  not found to check `prefers-reduced-motion`/`AccessibilityInfo.
  isReduceMotionEnabled()` anywhere during the UX audit, so treat this
  as a genuine open question, not a re-confirmation of existing
  handling.

## Keyboard/focus (web, if `map.web.tsx`'s placeholder path or any web
build is in scope)

- Tab through interactive elements; confirm a visible focus ring and a
  logical tab order. Lower priority given the web experience is
  currently a placeholder screen for Map specifically (native map
  libraries don't bundle for web), not full parity.

## After running this

Record pass/fail per screen/check (screen recordings with VoiceOver/
TalkBack audio are the strongest evidence). Any failure is a bucket-4
narrow bugfix PR — see matrix Section 12. Update matrix Section 7.
