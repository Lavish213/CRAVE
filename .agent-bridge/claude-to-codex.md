# H-20260914-wifi-only-upload-gating

Status: ready-for-review
Owner: Claude
Branch: claude/wifi-only-upload-gating
Base SHA: 34c5346 (origin/main tip after PR #309)
Commit SHA: af34bd1 (original implementation commit b14f3f3, CodeRabbit-fix
commit af34bd1 on top -- see below)
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

CodeRabbit's actual review then landed with 3 real findings, all fixed
forward on this branch (not merged first, per the #307 lesson):
1. **Minor**: this file's and STATE.md's `Commit SHA` fields were left
   `pending` -- corrected above.
2. **Minor**: `uploadPreferencesStore`'s `false` default is live
   instantly, but the real persisted value only lands once
   AsyncStorage's rehydration resolves -- `runSyncPass` read
   `wifiOnlyVideoUploads` without waiting for that. Fixed with a new
   `waitForUploadPreferencesHydration()` export, awaited before the
   gate.
3. **Major**: connectivity returning while a pass was already running
   used to silently no-op; if that active upload then failed, nothing
   scheduled a further attempt beyond an unrelated future event. Fixed
   by recording the blocked call's userId and draining it once the
   active pass's `finally` clears `syncInFlight`.

## Verification

- `npx tsc --noEmit` -> clean.
- `npx jest --ci` -> 63/63 suites, 610/610 tests (10 new total: 8 from
  the original implementation, 2 more from the CodeRabbit fixes). Each
  new/changed behavior independently confirmed to fail on the pre-fix
  code via revert-and-rerun before restoring the fix.
- `git diff --check` -> clean.
- Backend untouched.

## Known gaps / risks

`npx expo install` couldn't reach the React Native Directory
compatibility-check host from this sandbox -- installed via plain
`npm install` instead, after independently confirming netinfo's
peer-dependency range against this repo's RN version.

## Next action

None needed from you -- doesn't touch your dashboard lane. CI green,
CodeRabbit's real findings addressed -- holding for the user's explicit
merge approval rather than auto-merging, per the standing correction
from #307. PR: #312.
