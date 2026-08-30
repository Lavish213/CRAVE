# H-20260829-ios-notification-modes
Status: ready-for-review
Owner: Codex
Branch: codex/notification-release-fix
Base SHA: f8a7f751d9837314ab02eeed326348db7d32249e
Commit SHA: 30a801e
Allowed next files: none until review

## Outcome
Fixed the confirmed native-launch warnings that CRAVE implemented background
fetch and remote-notification delegates without declaring their iOS background
modes. `app.json` now declares both modes and enables Expo's documented
background-remote-notification config option. Added a regression test for the
source configuration.

Classified, but did not conceal or locally patch, the separate persisted server
registration warning. CRAVE is on Expo SDK 54 with `expo-notifications`
0.32.17. Expo fixed the Keychain/rejection defect upstream in the SDK 55
package line (`expo-notifications` 55.0.13, expo/expo#43829). Pulling that native
fix safely requires an Expo SDK upgrade or a deliberately maintained patch;
neither belongs in this narrow configuration PR.

## Verification
- `npx jest src/config/appConfig.test.ts --runInBand` -> 1 passed.
- `npx tsc --noEmit -p .` -> clean.
- Disposable `npx expo prebuild --platform ios --no-install --clean` -> passed.
- `PlistBuddy -c 'Print :UIBackgroundModes' ios/CRAVE/Info.plist` -> `fetch`,
  `remote-notification`.
- `npm test -- --runInBand` -> 300 passed, 32 suites; Jest reported the known
  retained open handle after results and was manually stopped.

## Known gaps / risks
- A locked-device, signed physical-device push delivery/tap test is still
  required before the notification path can be called release-verified.
- The SDK 54 persisted-registration warning remains an upstream dependency
  issue. Do not suppress `console.error` as a substitute for the native fix.
- No application source, backend, Railway configuration, or push credentials
  changed.

## Next action
Independently inspect `30a801e`, rerun the config test/typecheck, and verify a
fresh prebuild contains both modes. If correct, approve the PR; keep the SDK 55
upgrade/physical push test as explicit follow-up work.
