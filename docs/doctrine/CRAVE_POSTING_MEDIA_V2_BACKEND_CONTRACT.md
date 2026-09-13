# CRAVE Posting / Media V2 — Backend Contribution Contract

Status: **CANONICAL V1 BACKEND CONTRACT — APPROVED 2026-09-09**

Governing architecture: `CRAVE_POSTING_MEDIA_V2_ARCHITECTURE.md`

## 1. Why this contract exists

The current backend has strong adjacent primitives but no canonical native Posting object in the registered SQLAlchemy model set.

Existing authorities include:

- `VisitEvidence` — factual place experience; explicitly not preference.
- `PlaceImage` — place-scoped image transport/processing/moderation/gallery state.
- `PlaceVideo` — place-scoped video transport/processing/moderation state.
- `ActivityEvent` — current social activity ledger for ranking/follow activity; not a post body.
- `PlaceRanking` — ranking/preference authority.
- `DiscoveryCandidate` — missing-place discovery/promotion.
- report/block/moderation primitives.

None of these should be overloaded into a fake Post model. Posting V2 therefore adds one narrow orchestration record that represents the user's committed contribution while continuing to reference the existing media/evidence authorities.

## 2. Model: `FoodContribution`

Recommended V1 name: `FoodContribution`.

Reason: one object can represent a private log or a social/public food contribution without pretending every private record is a public `Post`.

Minimum fields:

- `id: UUID/string36`
- `user_id: string128`
- `client_id: string64` — client-generated idempotency key, unique per owner/client submission contract
- `intent: private_log | social_post`
- `place_id: UUID/string36 | null`
- `candidate_id: UUID/string36 | null`
- `unresolved_place_name: string | null`
- `reaction: loved | good | not_for_me | null`
- `caption: text | null`
- `visibility: private | connections | public`
- `occurred_at: datetime`
- `status: pending_place | committed | hidden | deleted`
- `created_at`
- `updated_at`

### Restaurant-reference constraint

Exactly one restaurant identity state may be active at commit time:

- resolved: `place_id` set;
- pending missing place: `candidate_id` set;
- explicitly unresolved draft may remain local, but V1 server commit should not create an ambiguous public contribution with neither place nor candidate unless a later approved contract explicitly allows it.

For a private log, unresolved server-side commit is optional and should only be added if product requirements require cloud persistence before restaurant identification. Local durable drafts already cover this V1 recovery need.

### Visibility constraint

- `private_log` must commit with `visibility=private`.
- `social_post` may commit with `connections` or `public`.
- changing a private log into social content later is a deliberate explicit action, not an automatic state change.

## 3. Media association

Do **not** replace `PlaceImage` or `PlaceVideo` in V1.

Add narrow association capability from contribution to existing media records.

Recommended approach:

- `food_contribution_media`
  - `contribution_id`
  - `media_kind: image | video`
  - `image_id | null`
  - `video_id | null`
  - `dish_ref` only if/when a trustworthy dish entity exists
  - `sort_order`

Constraint: exactly one of `image_id` / `video_id` is set.

This preserves separate image/video processing while giving the product one `MediaAsset` relationship at the contribution boundary.

V1 normal path may still be single-media. The association shape allows multi-dish/multi-media later without rewriting the contribution object.

## 4. Missing-place handling

A contribution may be committed against a `candidate_id` and remain `status=pending_place`.

When the existing DiscoveryCandidate pipeline promotes that candidate:

1. resolve `candidate_id → place_id`;
2. update the contribution in one transaction;
3. clear `candidate_id`;
4. set `place_id`;
5. attach/complete deferred media transport using the resolved Place contract;
6. emit downstream visit/social evidence only when its normal validity conditions are met;
7. require no client recapture.

Candidate rejection/blocking must not delete the contribution/draft media silently. The client receives a recoverable state and may choose another restaurant or delete.

## 5. Commit endpoint

Recommended endpoint:

`POST /api/v1/contributions`

Request:

```json
{
  "client_id": "client-generated-id",
  "intent": "private_log",
  "place_id": "...",
  "candidate_id": null,
  "reaction": "loved",
  "caption": "optional",
  "visibility": "private",
  "occurred_at": "ISO-8601",
  "media": [
    { "kind": "image", "media_id": "..." }
  ]
}
```

Rules:

- `place_id` and `candidate_id` are mutually exclusive;
- `private_log → private` enforced server-side;
- social visibility requires media in V1;
- media must belong to the authenticated user when uploader ownership is available;
- referenced media must correspond to the resolved place when `place_id` exists;
- idempotent retry returns the existing contribution for the same authenticated owner + `client_id`;
- server never trusts `user_id` from request body; use authenticated identity.

## 6. Media timing

The product contract allows upload to begin before final commit, but media upload must not itself publish.

Transition-safe options:

### Existing-place composer

1. durable local draft;
2. resolve place;
3. request/upload media as unpublished/place-scoped media;
4. user finishes composer;
5. commit contribution referencing uploaded media;
6. only contribution visibility determines social publication.

If existing PlaceImage/PlaceVideo read paths currently expose approved uploads immediately, the implementation must add an unpublished/contribution-pending visibility gate before adopting early upload. Until that gate exists, delay public-surface eligibility until contribution commit.

### Candidate-place composer

Media remains durable locally while the candidate is unresolved unless a candidate-scoped staging upload contract is added. V1 does not require inventing a separate candidate-media backend merely to upload earlier.

## 7. Visit evidence emission

A successful committed contribution with a resolved `place_id` may emit/update `VisitEvidence` as **factual history**.

Rules:

- source identifies the contribution contract;
- `source_ref = contribution.id`;
- `occurred_at = contribution.occurred_at`;
- posting/logging does not imply positive preference;
- reaction is handled separately by preference/taste evidence authority;
- deleting/retracting the contribution follows the privacy/evidence deletion contract.

A `candidate_id` contribution cannot create place-scoped VisitEvidence until candidate promotion resolves to a real Place.

## 8. Reaction evidence

Structured reaction is explicit evidence:

- `loved` → positive explicit signal;
- `good` → positive/moderate explicit signal according to the canonical evidence resolver;
- `not_for_me` → negative explicit signal;
- null → no reaction signal.

Do not write reaction into `VisitEvidence` itself. That model correctly separates factual history from preference.

Do not derive reaction from caption/media/publication.

## 9. Social activity

`ActivityEvent` should remain an event ledger, not the post record.

After a `social_post` contribution becomes valid for its visibility/moderation state, an activity event may reference the contribution through payload or a future explicit column. Friend/social feed reads should resolve the contribution as the content authority.

Do not copy caption/media/visibility into ActivityEvent as the only persistent representation.

## 10. Moderation

Media moderation remains owned by `PlaceImage` / `PlaceVideo` and existing report/review services.

Contribution-level visibility must honor media moderation:

- pending-review media cannot be represented as fully published if policy says it is withheld;
- rejected media cannot satisfy the public/social media requirement;
- transport failure is not moderation rejection;
- moderation changes may hide a contribution's media/content without rewriting historical processing status.

If text/caption moderation is later required, add it to the contribution layer without conflating it with image/video processing state.

## 11. Deletion

Recommended initial endpoint:

`DELETE /api/v1/contributions/{id}`

Requirements:

- owner authorization;
- idempotent delete behavior;
- remove/hide social publication immediately;
- retract contribution-derived activity;
- propagate deletion/recommendation changes according to privacy/evidence contract;
- do not automatically delete canonical Place media if an asset has legitimately been promoted into an independently governed Place-media role in a future phase.

V1 should avoid automatic post-media → canonical Place-media promotion, so this distinction remains simple.

## 12. Read endpoints

Minimum V1 reads should follow actual UI needs rather than building a social platform API prematurely.

Likely bounded reads:

- `GET /api/v1/contributions/{id}` for recovery/status;
- owner history/Profile query for own committed logs/posts;
- social Feed integration for visible followed/public contributions;
- Place Detail social/media section as later PMV2-08 integration.

Do not add follower-count, like-count, comment-thread, repost, creator-analytics, or watch-time APIs.

## 13. Security boundaries

- authenticated owner comes from server auth context;
- media ownership validated before association;
- candidate/place IDs validated;
- visibility constraints enforced server-side, not merely in frontend;
- `client_id` idempotency scoped so one user's key cannot collide with/claim another user's contribution;
- blocked-user visibility uses existing block authority;
- no raw local URI enters server persistence;
- no public exposure of uploader-only moderation/internal keys.

## 14. Database / migration boundaries

V1 additive migration should be deliberately small:

- `food_contributions`
- `food_contribution_media`
- indexes for owner/time, place/time, candidate/status, visibility/status, and idempotency
- model registry exports

Do not merge image/video tables, rewrite VisitEvidence, or replace ActivityEvent in this migration.

## 15. Implementation order

1. migrate/create contribution models;
2. strict model exports/import verification;
3. service-layer commit validation/idempotency;
4. create/read/delete routes;
5. tests for privacy/visibility/media ownership/idempotency/place-vs-candidate constraints;
6. candidate promotion resolver integration;
7. VisitEvidence emission;
8. social ActivityEvent/feed integration only after contribution semantics are stable;
9. frontend commit wiring;
10. retirement of legacy attach-immediately bridge after composer parity.

## 16. Acceptance tests

Backend V1 is not complete until tests prove:

- private log cannot become public through malformed payload;
- social post without required media is rejected;
- place and candidate cannot both be set;
- retry with same client id does not duplicate contribution;
- another user's media cannot be attached;
- candidate contribution survives unresolved period;
- candidate promotion attaches without recapture;
- candidate rejection remains recoverable;
- contribution creates factual VisitEvidence only after a real place exists;
- reaction does not rewrite VisitEvidence into preference;
- deletion removes publication/derived social event safely;
- upload/processing/moderation state stays distinct from contribution visibility.

## 17. Explicit non-goals

Not in this V1 backend contract:

- cross-device server drafts;
- perceptual duplicate-media system;
- resumable/multipart transport platform;
- ML media quality ranking;
- creator economy/analytics;
- comments/reposts/likes;
- automatic canonical Place-media promotion;
- heavy dish-recognition inference.
