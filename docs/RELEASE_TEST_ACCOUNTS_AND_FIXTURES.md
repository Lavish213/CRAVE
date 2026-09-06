# Release test accounts and fixtures

Defines what test-account **state** device/accessibility/smoke-test
certification needs — not credentials. No passwords, tokens, or real
personal data belong in this file or in git at all; provision the
actual accounts through Supabase/Google/Apple sign-in directly and
keep credentials wherever this team already keeps operational secrets
(a password manager, Railway/EAS secret store) — never in the repo.

## Why this is separate from the runbooks

Every device/accessibility/smoke-test runbook assumes specific account
states already exist so certification time goes to actually exercising
flows, not manufacturing data on the fly mid-test.

## Required accounts

### 1. Anonymous / logged-out

Not an account — just the app in its signed-out state. Used for:
sign-in flow itself, any screen's signed-out `EmptyState` (Feed,
Craves, Rank, Profile all have one), Leaderboard's Friends-tab
sign-in gap (`docs/SCREEN_UX_FINDINGS_TRIAGE.md`, RELEASE DEFECT #3).

### 2. Fresh account (new sign-up)

A real Google or Apple test identity that has never signed into CRAVE
before. Needs: nothing pre-existing — this account's entire purpose is
exercising `profile-setup.tsx`'s onboarding flow and every screen's
true-empty state (no rankings, no saves, no Craves, no friends) as a
brand-new user would see it.

### 3. Established account

Needs, before certification begins:
- At least 5-10 ranked places (to exercise Profile's ranked-list
  headline copy, which branches on count, and to clear the
  recommendation-threshold gate mentioned on Profile).
- At least one saved place, one "Craves"-matched (social) entry, and
  one manually-added place (Craves' three-source list needs all three
  populated to actually exercise its full UI).
- At least one uploaded photo and one uploaded video, attached to a
  place this account can revisit in Place Detail.
- At least one follow relationship in each direction (this account
  follows someone, and is followed by someone) to exercise Friends
  Feed, follow/unfollow, and block/unblock on `user/[id].tsx`.
- Push notifications enabled, with a real registered device token.

This is the account most device/accessibility runbook steps should
default to using, since it's the only one where "real" content exists
to actually look at.

### 4. Disposable deletion account

A throwaway account, created fresh specifically for
`docs/RUNBOOK_FINAL_RELEASE_SMOKE_TEST.md`'s final step. Needs: enough
state to make deletion meaningful to verify (at least one ranking, one
save, one uploaded photo/video, one report filed) so Phase 7's deletion
scope can actually be confirmed against real rows, not an already-empty
account where "deletion succeeded" is trivially true. **Never reuse
this account after its deletion test runs** — that's the point of it
being disposable.

## What NOT to do

- Do not commit any of these accounts' credentials, tokens, or
  Supabase user IDs to this repo, in this file or anywhere else.
- Do not reuse a real personal account for certification testing —
  test-account data (photos, rankings, follows) will show up to other
  real users on Feed/Map/Leaderboard/Friends Feed unless these
  accounts are clearly disposable/isolated test identities.
- Do not certify account deletion against the "established account"
  above — that account's continued existence across certification
  runs is what makes it useful; deleting it defeats its purpose.

## Maintenance

If a future certification finding needs a new account state (e.g. a
blocked-relationship account, a specific tier distribution for
Leaderboard testing), add it here rather than improvising it during a
device-certification session.
