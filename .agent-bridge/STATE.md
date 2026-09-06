# Active agent state

Status: claimed
Owner: Claude
Branch: claude/phase1-identity-isolation
Base SHA: 6e32ba4 (main)
Commit SHA: (none yet)
Scope: Phase 1 of an 8-phase frontend production-hardening program (user-
directed) -- identity isolation only. Private-data React Query cache
isolation across sign-out/account switch, local component-state identity
resets (Profile/User Profile/Taste Profile + any others found in the
sweep), and replacing useLocation()'s `UserLocation | null` contract with
an explicit lifecycle state machine. Every claimed bug re-verified against
current code before being touched -- anything already fixed is left alone.
Explicitly NOT in scope: PR #127 (claude/project-grade-systems-review-4ot7d0,
untouched), PR #126, PR #128, and phases 2-8 of the larger program (Search
rebuild, per-screen hardening, analytics semantics, UX polish, performance,
release-regression matrix) -- each gets its own future claim.
Locked files (this pass only): app/_layout.tsx, src/stores/authStore.ts,
app/place/[id].tsx, app/friends-feed.tsx, app/leaderboard.tsx,
app/(tabs)/profile.tsx, app/user/[id].tsx (if present), app/taste-profile*
(if present), src/hooks/useLocation.ts, plus any other file the viewer-
scoped-query-key sweep turns up -- full list will be recorded in the
handoff, not guessed in advance.
Verification plan: manual code re-audit of every claim in the user's Phase
1 brief before editing; full frontend suite (tsc --noEmit + jest) after;
new tests for the account-switch/sign-out cache-isolation regression gate.
Next action: sweep the repo for every React Query key whose response
depends on the authenticated viewer, then implement.
