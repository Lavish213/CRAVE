# Physical-device certification runbook

Permanent runbook. Run against the **exact signed release candidate**
from `docs/RUNBOOK_EAS_SIGNING_PRODUCTION_BUILD.md` — not a dev build,
not Expo Go. One physical iPhone and one physical Android device,
minimum.

Each row: the flow, what "pass" looks like (grounded in the actual
implemented behavior per `docs/SCREEN_INVENTORY_UX_DESIGN_AUDIT_2026-09-06.md`
and `docs/SCREEN_UX_FINDINGS_TRIAGE.md`, not a generic assumption), and
what evidence to capture (screen recording preferred over a still
screenshot for anything with a transition/permission dialog).

## Auth and account lifecycle

| Flow | Pass criteria | Evidence |
|---|---|---|
| Fresh install → sign in (Google) | Reaches an authenticated state; matches `docs/RUNBOOK_SUPABASE_PRODUCTION.md` Proof 3 | Screen recording |
| Fresh install → sign in (Apple) | Same | Screen recording |
| Sign out | Two-step confirm (`settings.tsx`), returns to signed-out state | Screenshot of confirm dialog |
| Account deletion | Two-step confirm with accurate scope copy; on success, signs out; on failure, session stays alive with a retry toast (not a false "deleted" state) | Screen recording, backend confirmation the account/data is actually gone |
| Login persistence across app restart | Still signed in after force-quit and relaunch | — |
| Account switch isolation | No prior account's saves/media/outbox state visible after switching accounts on one device | Screen recording of the switch |

## Camera / microphone / media

| Flow | Pass criteria | Evidence |
|---|---|---|
| Camera+mic permission — allow | Recording UI works, per `record-video/[placeId].tsx` | Screen recording |
| Camera+mic permission — deny (askable) | Shows "Allow Access" prompt; tapping requests again | Screenshot |
| Camera+mic permanently blocked | Shows "Open Settings" (not a dead "Allow Access"); tapping opens OS Settings; granting there and returning is recognized | Screen recording — this exact flow was a P1 fix earlier this session, worth double-confirming on real hardware |
| Video recording start/stop/cancel | Correct circle-to-square record/stop metaphor; cancel produces no queued video | Screen recording |
| **Failed recording** (RELEASE DEFECT #2 in the triage doc) | Confirm whether this has been fixed before running this check — as of the audit, a failed `recordAsync()` produces no user-facing error at all | Screen recording attempting to reproduce (e.g. force an error) |
| Video upload success | Toast confirms, appears in Craves/Place Detail afterward | — |
| Video upload with connectivity loss mid-upload | Queues as retryable (`failed` state), not silently lost; retries on reconnect | Screen recording spanning the disconnect |
| Photo upload | Same lifecycle expectations as video | — |
| Missing local file before sync (edge case) | No orphaned backend row, folds into `missing_local_file` state, not a crash | Hard to trigger manually — spot-check only if time allows |

## Location

| Flow | Pass criteria | Evidence |
|---|---|---|
| Location permission — allow | Map/Feed/add-spot use real location | Screenshot |
| Location permission — deny (askable) | Add Spot shows request-again prompt; Feed/Map silently omit distance (confirmed acceptable per the audit, not a regression to fix here) | Screenshot |
| Location permanently blocked | Add Spot shows "Open Settings"; Feed/Map degrade gracefully | Screen recording |
| Location revoked after prior grant (OS Settings, mid-session) | App detects the revocation on next foreground, doesn't keep using stale "granted" state | Screen recording: grant → background → revoke in OS Settings → foreground |

## Notifications

| Flow | Pass criteria | Evidence |
|---|---|---|
| Notification permission prompt | Matches Settings' 4-state model (`granted`/`denied`/`undetermined`/`unavailable`) | Screenshot |
| Real push receipt | Per `docs/RUNBOOK_PUSH_NOTIFICATIONS_PRODUCTION.md` Proof 3 | Screen recording of the notification arriving and being tapped |

## Background/foreground and connectivity

| Flow | Pass criteria | Evidence |
|---|---|---|
| Background during upload → foreground | Upload continues or resumes correctly, no corrupted/duplicate state | Screen recording |
| Background during video recording → foreground | No crash; recording state handled sanely (confirm actual current behavior — not separately audited yet) | Screen recording |
| Full offline app launch | Explicit offline/error state shown, no blank screens or fake success | Screenshot |
| Network loss mid-flow (ranking submit, save, upload) | Retries/recovers without duplicating the action (Phase 4/5's idempotency work — this is the real-device confirmation of what was unit-tested) | Screen recording |
| Reconnect after offline | State reconciles (queued actions flush) without duplication | Screen recording |

## Known findings to specifically re-check on real hardware

Per `docs/SCREEN_UX_FINDINGS_TRIAGE.md`'s RELEASE DEFECT list — these
were found by static code reading, not device testing, so confirm
they reproduce (or have already been fixed) on the real signed build:

1. Rank's error-state "retry" button actually just navigates back.
2. `record-video`'s failed recording produces no user-facing error.
3. Leaderboard's Friends tab shows generic empty copy instead of a
   sign-in prompt when signed out.

## After running this

Record pass/fail per row (screenshots/recordings as evidence per
`docs/MASTER_RELEASE_CERTIFICATION_MATRIX.md`'s evidence conventions).
Any failure is a bucket-4 narrow bugfix PR — see matrix Section 12.
Update matrix Section 6.
