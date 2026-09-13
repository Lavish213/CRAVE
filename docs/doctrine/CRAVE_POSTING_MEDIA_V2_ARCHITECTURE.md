# CRAVE Posting / Media V2 Architecture

Status: **CANONICAL V1 ARCHITECTURE OVERLAY — APPROVED 2026-09-09**

## 1. Purpose

This document defines the target V1 architecture for CRAVE native posting and private food logging. It supersedes older Posting assumptions that require a live `place_id` before captured media can survive, that treat photo and video as separate product flows, or that expose infrastructure screens such as `food-evidence`, `record-video/[placeId]`, and `add-spot` as the permanent composer.

This architecture is deliberately incremental. CRAVE already has strong media-upload, video-offline, moderation, reporting, blocking, and missing-place primitives. V1 extends and unifies those systems instead of replacing working infrastructure.

## 2. Core doctrine

The permanent flow is:

`Capture → Draft → Identify → Describe → Choose Visibility → Commit → Upload/Process → Resolve → Publish`

The following concepts must remain distinct:

- capture ≠ upload;
- upload ≠ publish;
- processing ≠ moderation;
- moderation ≠ upload failure;
- visit ≠ positive preference;
- media ≠ positive preference;
- caption ≠ Rank evidence;
- candidate restaurant ≠ verified Place;
- private log ≠ public/social post.

### Non-negotiable invariants

1. **Capture once. Never require recreation after a recoverable failure.**
2. **Photo and video share one MediaAsset product contract while retaining specialized processors underneath.**
3. **Media belongs to a durable Draft before it belongs to a Place, Post, or public surface.**
4. **Restaurant identity may be `place`, `candidate`, or `unresolved`. Missing CRAVE data never destroys the contribution.**
5. **Existing upload, moderation, account-isolation, discovery, reporting, and blocking infrastructure is extended, not rebuilt.**
6. **V1 fixes durability, identity resolution, composition, privacy, and recovery. Scale infrastructure is earned by actual usage.**

## 3. Repository-grounded baseline

The following already exists and is reusable:

- `frontend/app/record-video/[placeId].tsx`: Expo Camera video capture, camera/microphone permissions, permission-blocked recovery, recording failure feedback, local recording, templates/beat cues, and a 10-second default limit.
- `frontend/src/stores/videoQueueStore.ts`: durable local video copy, persistent account-scoped queue, retry/backoff, idempotent client identifiers, missing-local-file handling, and direct signed upload handoff.
- `frontend/src/api/videos.ts`: signed direct-to-storage upload, confirmation, status/feed/template APIs, processing vocabulary.
- `frontend/src/api/upload.ts` / `useUploadImage`: image request → signed PUT → confirm path with moderation and processing states.
- `frontend/app/add-spot.tsx`: existing-place lookup, GPS-assisted nearby search, and `DiscoveryCandidate` submission for missing places.
- existing moderation/report/block primitives: photo/place reporting, moderation states, and user block/unblock.

Posting V2-A already landed on `main` in PRs #244/#245:

- additive `GET /nearby/candidate/{candidate_id}/status` for candidate promotion resolution;
- durable local `postingDraftStore.ts`;
- `restaurantRef: unresolved | candidate | place`;
- durable photo/video capture before restaurant resolution;
- automatic candidate → Place resolution on sign-in/foreground;
- food-evidence now passes a `draftId`, not raw media route parameters.

These are the new baseline. They are not temporary experiments to be discarded during composer work.

## 4. Unified MediaAsset contract

At the product-domain boundary, photo and video are both `MediaAsset`.

A V1 MediaAsset needs the following semantics even if implementation remains split across existing stores:

- `id`
- `ownerId`
- `type: image | video`
- `source: camera | library`
- `localUri`
- `mimeType`
- `fileSize`
- `width` / `height` where available
- `durationMs` for video where available
- `thumbnailUri` where useful
- `createdAt`
- transport state
- processing state
- moderation state

### Transport states

`local | queued | uploading | uploaded | failed`

### Processing states

Media-type-specific processing may continue to use specialized vocabularies. A caller must never infer moderation or publication from transport state.

### Implementation boundary

V1 does **not** require one monolithic media table or one processor. The product contract is unified; the image and video processing paths may remain specialized beneath it.

## 5. Durable PostingDraft

The composer owns a durable local `PostingDraft`.

Minimum target fields:

- `id`
- `ownerId`
- `intent: private_log | social_post`
- `media[]`
- `restaurantRef`
- `dishes[]`
- `reaction: loved | good | not_for_me | null`
- `caption`
- `visibility: private | connections | public | unset`
- `visitTime`
- `state`
- `createdAt`
- `updatedAt`

Target draft states:

`editing | ready | committing | pending_place_resolution | committed | failed`

V1 local persistence is sufficient. A heavy server-side draft system or cross-device draft synchronization is not required unless later product evidence justifies it.

## 6. Restaurant reference

Restaurant identity is a state, not a capture prerequisite.

### Existing CRAVE place

`{ type: 'place', placeId }`

### Submitted missing place

`{ type: 'candidate', candidateId, displayName }`

### Not yet identified

`{ type: 'unresolved', displayName? }`

A draft may continue to exist in any of these states. Public/private commit rules may require more information before final publication, but the media itself must remain safe.

## 7. Missing-place resolution

The old failure mode is prohibited:

`capture → missing restaurant → candidate created → no place_id → tell user to come back and recreate media`

The target flow is:

`capture → durable draft → submit missing restaurant → restaurantRef=candidate → continue/save → candidate later promoted → candidate status resolves to place_id → contribution attaches automatically`

The user must never be required to recapture or reselect media solely because CRAVE had not yet promoted a restaurant into `Place`.

If a candidate is blocked/rejected, the draft must remain recoverable and explain the truth. It must not silently disappear.

## 8. Entry and intent

The persistent `+` remains the canonical entry.

It presents two clear intentions:

- **Log what I ate** — private-first personal food history.
- **Share a food find** — social/public contribution.

These are distinct outcomes using one shared composer state machine.

A private log may omit media. A connections/public post requires media.

## 9. Composer sequence

Canonical V1 sequence:

`Intent → Capture/Media → Preview → Restaurant → Dish (when available) → Reaction → Caption → Visibility/Review → Commit`

### Media

One capture surface with:

- Photo mode
- Video mode
- Library

Photo/video are modes, not separate products.

### Preview

Media must be visible before proceeding. V1 supports retake/replace and basic video playback. It does not require creator-grade editing.

### Restaurant

Identification may use known navigation context, recent CRAVE context, foreground location, nearby search, and manual search. Suggestions must be confirmed by the user.

Location improves suggestions but is never required to log/post.

### Missing restaurant

`Can't find it? Add this place` uses the existing `DiscoveryCandidate` pipeline and returns to the composer with `restaurantRef=candidate`.

### Dish

Dish confirmation is optional and capability-gated.

**Dish Intelligence is NOT a hard blocker for Posting V1.** When trustworthy structured dish/menu capability exists, surface suggestions and require confirmation. When it does not, omit the structured dish step or allow lightweight optional text; never fabricate a dish entity.

### Reaction

The structured quick take is:

- Loved it
- Good
- Not for me
- Skip

This is explicit preference evidence. Visit/media/caption remain separate signals.

### Caption

Optional. Caption is expression/context, not Rank authority.

### Visibility

Visibility is always explicit before commit:

- Just me
- Connections / approved-follow scope
- Public

The final review state must state the consequence in words, e.g. `Saving privately` or `Posting publicly`. Do not rely on color or iconography alone.

## 10. Commit semantics

Evidence is emitted only after successful user commit.

Capture, upload completion, restaurant selection, and media processing must not independently create a public post or durable preference claim.

Conceptually a committed contribution contains:

- owner
- intent
- restaurant reference / resolved place
- visit timestamp
- dish references where valid
- media references
- reaction
- caption
- visibility

Downstream systems consume only the evidence their contracts permit.

## 11. Upload and processing

Media transport may begin while the user completes restaurant/dish/reaction/visibility steps, provided publication remains impossible before explicit commit.

Existing signed-upload architecture is retained.

### Photo

Photo must use durable-local-first behavior before network, matching the resilience class already provided to video.

### Video

Retain the proven `videoQueueStore` guarantees: durable file, account-scoped sync, retry/backoff, idempotency, failure visibility, and asynchronous processing.

### Deferred scale work

Resumable/multipart upload is Phase 2 unless real failure data demonstrates it is necessary for V1.

## 12. Account isolation

Generalize the existing video ownership rule.

A draft/media asset created by Account A may never upload or publish as Account B after an account switch. Sign-out must not transfer ownership. Drafts remain isolated until the original owner returns or explicitly deletes them.

## 13. Moderation and safety

CRAVE already has moderation primitives. Posting V2 extends them.

Keep these vocabularies separate:

- transport/upload state
- processing state
- moderation state
- publication state

Public Posting must support the existing app-level UGC safety model, including reporting, blocking, delete-own-content behavior, and clear moderation outcomes.

A moderation rejection must not be presented as an upload failure. Where safe and appropriate, surface a truthful reason category and next action.

## 14. Failure and recovery

The composer must never default to `start over` for recoverable failures.

Required recoverable cases:

- offline capture;
- upload failure;
- app background/foreground;
- app termination after durable capture;
- unresolved restaurant;
- pending candidate promotion;
- candidate blocked/rejected;
- account refresh/switch isolation;
- processing delay/failure;
- moderation pending/rejected;
- storage pressure/missing local file.

Failure UX should offer the smallest truthful next action: retry, replace media, continue draft, choose another restaurant, keep private where valid, or delete.

## 15. Draft lifecycle

Drafts must survive recoverable interruptions.

The product may surface `Continue your draft` when useful, but must not create re-engagement pressure or nagging.

V1 must define cleanup behavior for abandoned local media so multi-MB files are not retained forever. Recently created media that CRAVE told the user was saved must not be silently removed.

## 16. Deletion and evidence propagation

Deleting a draft removes its local media and cancels queued unpublished work where technically possible.

Deleting a committed post/log removes publication according to the privacy contract and retracts/recomputes derived evidence where required. Deleted public content must not remain an invisible personalization signal indefinitely.

## 17. Post media vs Place media

User-post media and canonical Place media are separate concepts.

V1 may display approved user media contextually, but uploading a post does not automatically make that asset a canonical Place hero/photo.

Automated quality promotion from post media into Place media is Phase 2.

## 18. Privacy

Posting does not justify background location collection.

Foreground location is optional assistance for restaurant identification.

Published media derivatives must not expose unnecessary sensitive metadata such as precise EXIF GPS coordinates. Public association is the selected restaurant/place, not the photographer's raw capture coordinate.

Visibility and publication consequences must remain explicit.

## 19. Accessibility

Design requirements:

- camera and media controls have accessible labels/roles;
- recording state is not color-only;
- controls meet minimum touch-target requirements;
- Photo/Video mode is understandable to screen readers;
- errors and important state changes are announced appropriately;
- library/manual-search alternatives exist when camera/location are unavailable;
- visibility meaning is textually explicit;
- large text and reduced motion are supported;
- no gesture-only required operation.

Runtime verification occurs after implementation on real devices and is not claimed by this architecture document.

## 20. Explicit V1 exclusions

The following are not V1 blockers:

- perceptual-hash duplicate infrastructure;
- sophisticated duplicate-media ranking;
- resumable/multipart uploads unless field data proves necessary;
- automatic post-media → canonical Place-media promotion;
- ML media quality ranking;
- creator analytics;
- filters/stickers/music/effects;
- template marketplace;
- remix/duet/stitch mechanics;
- comments/reposts/public like counts;
- follower-count optimization;
- cross-device drafts;
- heavy visual dish recognition.

Existing BeatCue/video-template code is preserved but demoted from primary composer UX until evidence shows it improves food-evidence quality.

## 21. Migration waves

### PMV2-00 — Doctrine & inventory

Freeze architecture, screen contract, file disposition, evidence/privacy boundaries, and migration rules.

### PMV2-01 — Durable Media Foundation

Generalize durable-local-first media behavior and preserve owner isolation. PR #245 establishes the first implementation slice and is the baseline for subsequent work.

### PMV2-02 — Restaurant Reference

Support `place | candidate | unresolved` and candidate→Place resolution. PRs #244/#245 establish the first implementation slice and are the baseline.

### PMV2-03 — Posting Draft

Expand durable draft state from the current media/restaurant core to intent, dish/reaction/caption/visibility/timestamp and recovery lifecycle.

### PMV2-04 — Unified Capture

Rebuild the permanent capture experience around Photo | Video | Library while preserving proven camera/permission mechanics.

### PMV2-05 — Composer

Implement Preview → Restaurant → Dish-if-available → Reaction → Caption → Visibility → Commit.

### PMV2-06 — Transport & Recovery

Unify user-facing upload/retry/offline/draft recovery behavior while retaining specialized media processors.

### PMV2-07 — Moderation & Privacy

Extend existing moderation, reporting, blocking, deletion, metadata, and visibility semantics to the new contribution flow.

### PMV2-08 — Integration

Connect committed evidence to Feed/Taste/Visit/Rank/Profile/Place Detail without semantic leakage.

### PMV2-09 — Retirement

Retire old UX ownership only after parity, deep-link migration, and zero callers are proven.

### PMV2-10 — Certification

Run automated regression, runtime accessibility, real-device camera/media, offline/recovery, and privacy/state QA.

## 22. File disposition

- `frontend/app/food-evidence.tsx` — **REBUILD**, then retire standalone authority after composer parity.
- `frontend/app/record-video/[placeId].tsx` — **ADAPT/MERGE** capture capability; retire restaurant-first product ownership after parity.
- `frontend/app/add-spot.tsx` — **KEEP** missing-place capability; remove permanent Posting-orchestrator responsibility.
- `frontend/src/stores/postingDraftStore.ts` — **KEEP/EXTEND** as the current durable-draft baseline.
- `frontend/src/stores/videoQueueStore.ts` — **KEEP/GENERALIZE**; do not discard proven resilience.
- `frontend/src/api/videos.ts` — **KEEP/ADAPT**.
- `frontend/src/api/upload.ts` / `useUploadImage` — **KEEP/ADAPT** into durable-media architecture.
- Expo Camera / ImagePicker — **KEEP**.
- signed uploads / backend video processor — **KEEP**.
- `DiscoveryCandidate` promotion pipeline — **KEEP/EXTEND relationship contract**.
- existing moderation/report/block — **KEEP/EXTEND**.
- BeatCue/templates — **DEMOTE/INVESTIGATE**, not a default V1 composer dependency.

## 23. Implementation boundary

Codex/implementers may solve technical details locally but may not silently invent product semantics, privacy defaults, visibility behavior, evidence meaning, or missing data.

**Implement the approved composer. Do not redesign it. Do not invent missing product semantics.**

The goal is not zero unknowns. It is zero invisible unknowns.
