# H-20260914-wifi-only-upload-gating

Status: ready-for-review
Owner: Claude
Branch: claude/wifi-only-upload-gating
Base SHA: 34c5346 (origin/main tip after PR #309)
Commit SHA: pending (see PR for the authoritative head SHA once pushed)
Allowed next files: none from me pending PR review.

## Outcome

Third of the four offline-upload-UX follow-ups: Wi-Fi-only video upload
gating. Added a real `@react-native-community/netinfo@12.0.1` dependency
(no fake detection). New `uploadPreferencesStore.ts` holds one persisted
preference (`wifiOnlyVideoUploads`, default off -- turning it on by
default would silently stop cellular uploads with no explanation, a
regression rather than a new opt-in feature). `videoQueueStore.ts`'s
`runSyncPass` checks real connection type only when the preference is
on; a `NetInfo.addEventListener` listener re-attempts a pass on any
connectivity change (mirrors the existing `AppState` foreground
listener). New Settings toggle row.

## Verification

- `npx tsc --noEmit` -> clean.
- `npx jest --ci` -> 63/63 suites, 608/608 tests (8 new). Each new/changed
  behavior independently confirmed to fail on the pre-fix code via
  revert-and-rerun before restoring the fix.
- `git diff --check` -> clean.
- Backend untouched.

## Known gaps / risks

One follow-up remains after this: merging the local queue into
`PlaceVideoGallery`'s server feed. `npx expo install` couldn't reach the
React Native Directory compatibility-check host from this sandbox --
installed via plain `npm install` instead, after independently
confirming netinfo's peer-dependency range against this repo's RN
version.

## Next action

None needed from you -- doesn't touch your dashboard lane. Waiting for
CodeRabbit's actual findings (not just CI-green) before merging, per the
standing correction from #307.
