# Decision Session — spec (Phase 1, narrow slice)

Status: **shipped end-to-end (2026-08-27)**. Backend implemented by
Claude (`24a1b89`); frontend implemented by Codex against this doc's
frozen contract (`codex/decision-session-frontend`), reviewed and
merged by Claude (`6f2177b`) after independently re-running the full
suite (279/279) and `tsc --noEmit` against the merged tree. Not yet
device-verified — see CRAVE_STATUS.md's "needs your action" list.

## Why this exists

Both `docs/doctrine/CRAVE_DECISION_INTELLIGENCE_ARCHITECTURE.md` and a
second, independent product audit converged on the same idea: CRAVE's
home experience should resolve a craving into 3 meaningfully different
options — **best fit**, **safe bet**, **wildcard** — each with a reason,
instead of a long generic list. This is the smallest testable slice of
that idea: no new ranking model, no LLM, no hard-constraint intent
parsing yet. It reuses the scoring/diversity work `feed_ranker.py`
already does and just *selects 3 roles* out of what that already
produces.

Explicitly not in scope here (later phases, per doctrine): outcome
capture (visited / would-get-again), free-text explanations, taste
learning, group decisions.

## Backend (implemented)

**Endpoint**: `GET /api/v1/decision-session`

Query params: `city_id?`, `lat?`, `lng?`, `radius_miles?` (default 20,
same bounds as `/places`) — identical shape to `/places`' own
location/city params, reusing the same candidate-retrieval functions
(`list_places_near`, `get_feed_places`, `query_list_places`) so this
endpoint never diverges from Feed's own idea of "what's nearby."

**Response**:
```json
{
  "cards": [
    {
      "place": { /* PlaceOut — identical shape to /places' items[] */ },
      "role": "best_fit",
      "reason_codes": ["top_ranked_in_area"]
    },
    {
      "place": { /* PlaceOut */ },
      "role": "safe_bet",
      "reason_codes": ["high_percentile", "close_by"]
    },
    {
      "place": { /* PlaceOut */ },
      "role": "wildcard",
      "reason_codes": ["underrated_pick", "different_cuisine"]
    }
  ],
  "degraded": false
}
```

`cards` has **0 to 3 entries** — never pad with duplicates or
lower-quality filler to force 3. `degraded: true` means fewer than 3
roles could be filled from real diversity (thin candidate pool for
that area) — **the frontend must render however many cards are
present, never assume exactly 3.**

**Role selection logic** (`app/services/decision_session/decision_session_builder.py`):
1. Run candidates through the existing `feed_ranker.rank_feed()` — same
   scoring/diversity every Feed request gets, so a "decision session"
   pick is never contradicted by what Feed itself would show.
2. **Best fit** — rank #1 post-diversity.
3. **Safe bet** — the highest-ranked remaining candidate with
   `rank_percentile >= 0.80` (the existing "gem"/"crave_pick" tier
   threshold — see `places.py::_rank_to_tier`) from a *different*
   primary category than best_fit. If none qualifies, no safe_bet card
   (never lower the bar to force one).
4. **Wildcard** — the highest-ranked remaining candidate that received
   `feed_ranker`'s existing deterministic explore-boost (the same
   CRC32-seeded ~15% pool used for Feed's own exploration), from a
   category distinct from both other picks. If none qualifies, no
   wildcard card.
5. Reason codes are derived directly from fields already computed here
   (percentile, distance, explore-boost membership, category
   distinctness) — never free text, never an LLM call. This keeps
   "explainable" meaning *reconstructable from logged fields*, per the
   doctrine's own definition, not a vibe.

**Ledger logging** — new surface `"decision_session"` added to
`VALID_SURFACES` (one-line addition, matches the model's own stated
extension pattern). New nullable column `decision_role` on
`recommendation_events` (migration `add_decision_role_to_recommendation_events`)
— holds `"best_fit" | "safe_bet" | "wildcard"`, set only on
`surface=decision_session` rows. Existing `event_type`s reused
(`impression`, `click`) — no new event type needed for this slice.

## Frontend (not started — build against the contract above)

1. New hook `src/hooks/useDecisionSession.ts` — calls
   `GET /api/v1/decision-session` with the same params `useLocation`/
   `useCityStore` already provide to Feed. React Query, same
   conventions as `useTrending`/`useRecommendations`.
2. New section at the top of `app/(tabs)/index.tsx` (**above** the
   existing tier-bucketed list — do not replace Feed, this is additive
   and sits alongside it): renders 1-3 cards, each showing the
   existing `PlaceCard` (add an optional `role` prop that renders a
   small label — "Best fit" / "Safe bet" / "Wildcard" — reuse the
   component, don't fork a new one) plus one reason code as a caption
   (a small static string-map from reason code -> human copy, e.g.
   `top_ranked_in_area` -> "Top pick near you").
3. Logging: on load, `logRecommendationEvents` one `impression` per
   card actually rendered, `surface: 'decision_session'`,
   `decision_role` set, `position` = card's index (0/1/2),
   `rank_percentile` from the card's place. On tap, one `click` event,
   same fields, before navigating to place detail. Reuses
   `recommendationEventQueue.ts` exactly as-is — no new plumbing there.
4. Empty/degraded state: 0 cards → render nothing (don't show an empty
   section header); 1-2 cards → render only what's there, no
   placeholder for the missing role.

**Tests** (mirror `frontend/__tests__/feed.test.tsx` conventions):
mock the endpoint, assert the right number of cards render for
0/1/2/3-card responses, assert impression events fire with correct
`role`/`position`, assert a tap logs `click` and navigates.

## Acceptance criteria

- Backend: unit tests cover best_fit/safe_bet/wildcard selection
  independently, the insufficient-candidates degrade path, and that
  `decision_session` events validate through the existing
  `record_events` pipeline unchanged.
- Frontend: renders correctly for 0/1/2/3 cards, never crashes on a
  thin result, logs impression/click with the right role.
- Metrics this unlocks once live (query the Ledger directly, no new
  dashboard needed for v1): click-through rate per role (does
  "wildcard" ever get picked — the one thing this mechanic can't fake),
  position-independent role comparison.
