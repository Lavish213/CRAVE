# H-20260902-legal-docs-and-expo-55

Status: ready-for-review
Owner: Claude
Branch: claude/project-grade-systems-review-4ot7d0
Base SHA: d4510e3 (main, restarted -- old branch of this name carried
no unique commits)
Commit SHA: bb744cad3be96b18f47689781bf88c67204a6a1
Allowed next files: none from me -- docs-only bridge handoff, no more
code planned on this branch right now.

## Outcome

Two independent, code-only Product-lane passes (no Railway/Supabase
access used).

**Legal docs (eb7f657, d4510e3):** `docs/privacy-policy.md` and
`docs/terms-of-service.md` are the source docs for the hosted URLs App
Store Connect requires; both still had `[DATE]`/`[YOUR CONTACT EMAIL]`
placeholders (privacy also had an unresolved account-deletion-retention
bracket). Filled in from verified sources, not guesses: date/contact
synced to the already-shipped in-app copy
(`frontend/app/legal/{privacy,terms}.tsx` -- `hello@crave.app`, August
25, 2026), and the retention language now matches what
`backend/app/services/account/account_deletion_service.py` actually
does. Left ToS §12's governing-law jurisdiction as an open placeholder
on purpose -- real business decision, not something to invent.

**Expo SDK 54->55 upgrade (bb744ca):** bumped every `expo-*` package
plus `react`/`react-dom`/`react-native` and native-module siblings
(reanimated, screens, gesture-handler, maps, worklets) to the exact
versions SDK 55 bundles -- read directly out of the installed `expo`
package's own `bundledNativeModules.json`, not guessed. Fixes
`expo-notifications`' known Keychain/persisted-registration read bug
(0.32.17), fixed upstream only in the SDK 55 line (expo/expo#43829) --
the reason this was on the backlog. Two real dependency-resolution bugs
found and fixed along the way: `@expo/vector-icons`'s unbounded
`expo-font` peer dependency was auto-installing the newest published
`expo-font` (SDK 57's line) instead of 55's, breaking `expo-asset`
resolution -- now pinned explicitly. Regenerating `package-lock.json`
also let `@shopify/flash-list` float from its deliberately-locked
`2.0.2` to an ESM-only `2.3.2` that broke Jest -- reverted to the exact
pin. `@testing-library/react-native` needed a real bump (12.9.0 ->
13.3.3, not the newer 14.x line) because `expo-router@55` now
peer-requires `>=13.2.0`.

## Verification

- `npx tsc --noEmit` -> clean, no errors.
- `npx jest` -> 331 passed, 34 suites (unchanged count from before the
  upgrade).
- `npx expo config --type public` -> resolves `sdkVersion: '55.0.0'`
  with no plugin/schema errors against the existing `app.json`.
- `npm audit` -> 19 moderate findings, all build-tooling-only (same
  class as previously documented, down from 26, nothing high/critical).

## Known gaps / risks

- Neither legal doc has an actual hosted URL yet -- that and a lawyer's
  pass are the user's action, not code.
- The Expo SDK 55 upgrade is unverified at the native/device level: no
  EAS build or prebuild has run against these versions anywhere (this
  session is a Linux container, no Xcode/simulator), and the Keychain
  bug this targets has never been reproduced or disproven on a real
  device in this project. Code-level proof only.
- This branch has no PR open yet (wasn't asked for). It carries no
  other pending code work from me.

## Next action

Codex: this pass didn't touch any of your still-open Production-lane
items (menu/image canary retries, `image_processing_recovery`
synthetic test, `run_phase4_batch.py` usage) -- see
`CRAVE_STATUS.md`'s "What's next -- pick a track" section for the
current, canonical list of those; nothing here supersedes it. If you
pick up this branch: an EAS build/prebuild against the SDK 55 bump,
ideally followed by a real device install, is the one thing that would
actually close this pass's remaining gap.
