# CRAVE Screen Contract — Posting / Private Logging V2

Status: **GREEN FOR V1 IMPLEMENTATION — 2026-09-09**

Governing architecture: `CRAVE_POSTING_MEDIA_V2_ARCHITECTURE.md`

## 1. Purpose

The Posting composer captures high-quality food evidence and lets the user choose whether that evidence becomes a private food log or a social/public contribution. It must make capture fast, preserve the user's work through recoverable failures, and never confuse upload with publication.

The composer is not a creator studio, review form, engagement surface, or place-submission utility.

## 2. User objective

Primary objective:

> Record what I ate without losing the media or being forced to recreate it.

Secondary objective:

> Share a food find intentionally with the audience I choose.

## 3. Entry points

Canonical entry:

- persistent `+` action.

Contextual entries may include:

- Place Detail fast path with a known `place_id`;
- existing record-video deep link during migration;
- recovery/Activity entry into an unfinished or failed draft.

All entry points converge on the same composer state model. A contextual place may prefill restaurant identity but must remain user-correctable before commit.

## 4. Exit outcomes

Successful exits:

- private log committed;
- connections/public post committed;
- draft safely saved for later;
- user intentionally deletes draft.

Failure must not silently discard durable media.

## 5. First viewport / intent

The persistent `+` opens **Add to CRAVE** with two clear outcomes:

### Log what I ate

Private-first food history. Media optional.

### Share a food find

Social/public contribution. Media required before public/connections commit.

Do not present a generic visibility toggle as the only difference between these intentions.

## 6. Canonical flow

`Intent → Media → Preview → Restaurant → Dish (capability-gated) → Reaction → Caption → Visibility/Review → Commit`

The flow may collapse low-value steps when context is already known, but must never skip visibility confirmation for a social/public outcome.

## 7. PM-01 — Intent

### Required content

- Add to CRAVE title
- Log what I ate
- Share a food find
- close/back

### Behavior

Selecting intent creates/updates the durable draft before irreversible work begins.

## 8. PM-02 — Capture / Media

### Hierarchy

1. camera/media content dominates;
2. Photo / Video mode selector;
3. primary capture control;
4. Library;
5. camera flip where supported;
6. close/back.

### Rules

- Photo and Video are modes, not separate product routes.
- Library may return a supported image or video.
- Private log may skip media.
- Connections/public contribution may not commit without media.
- Camera permission is requested only when camera capture is used.
- Microphone permission is requested only when video recording requires it.
- Location permission is not required for capture.

### Prohibited

- giant utility menu of `Take Photo / Choose Photo / Choose Video` as the permanent V1 capture UI;
- mandatory creator templates;
- autoplay feed behavior;
- filters/music/stickers/effects.

## 9. PM-03 — Preview

### Image

- large media preview
- Retake/Replace
- Use Photo

### Video

- video preview/playback
- duration/audio state where relevant
- Retake/Replace
- Use Video

### Invariant

The accepted asset must already exist in durable app-owned storage before the composer claims it is saved.

## 10. PM-04 — Restaurant identification

Prompt: **Where was this?**

Suggested identities may use:

- contextual Place Detail source;
- recent CRAVE context;
- foreground nearby location when permission exists;
- nearby search;
- manual Search.

### Required actions

- select suggested/existing place;
- Search another restaurant;
- Can't find it? Add this place;
- save/continue later when restaurant remains unresolved where allowed.

### Location denied

Fall back to restaurant Search. Do not block Posting.

### Confirmation

A suggested restaurant is never silently accepted. User confirmation is required.

## 11. PM-05 — Missing restaurant

Use the existing `DiscoveryCandidate` capability.

Minimum information should stay small and truthful, such as:

- restaurant/place name;
- approximate address/location where available;
- optional category hint only if useful.

After successful candidate creation:

- set `restaurantRef=candidate`;
- return to the composer;
- keep durable media intact;
- explain `We're verifying this restaurant` or equivalent.

Never tell the user to come back later and recreate the photo/video.

## 12. PM-06 — Dish identification

Prompt: **What did you get?**

### When structured Dish Intelligence is available

- show trustworthy menu/dish suggestions;
- allow search/choose another;
- require confirmation of any inference.

### When unavailable/weak

- omit structured dish selection or allow optional lightweight text;
- provide Skip;
- never fabricate a Dish entity.

Dish Intelligence is not a Posting V1 blocker.

## 13. PM-07 — Reaction

Prompt: **How was it?**

Options:

- Loved it
- Good
- Not for me
- Skip

This is explicit structured preference evidence.

Do not derive the same meaning merely from media, visit, caption, or posting frequency.

## 14. PM-08 — Caption / context

Prompt: **Anything worth remembering?**

Caption is optional.

It may capture useful nuance but is weak evidence relative to explicit reaction/Rank and must never directly control Rank ordering.

Backdating/visit time may be edited in this stage or the final review, provided the choice remains understandable.

## 15. PM-09 — Visibility / final review

Visibility must be explicitly chosen before a social/public commit.

Options:

- Just me
- Connections / approved-follow scope
- Public

The screen must state the consequence in words:

- `Saving privately`
- `Sharing with connections`
- `Posting publicly`

No color-only privacy meaning. No tiny icon-only default.

## 16. PM-10 — Commit

The final action creates the durable contribution/log semantics.

### Evidence gate

No durable recommendation/preference evidence may be emitted merely because:

- media was captured;
- media uploaded;
- a place was selected;
- the user viewed the composer;
- a caption was typed.

Evidence emission happens after successful commit according to the Evidence Signal Hierarchy.

### Idempotency

Commit must be retry-safe and must not create duplicate contributions after timeout/retry.

## 17. PM-11 — Success

Success is brief and non-celebratory.

Examples:

- Saved privately
- Posted
- Restaurant verification pending

Primary exit returns the user to the most relevant source context or closes the composer. Do not create a posting streak/reward loop.

## 18. Durable state requirements

Draft state must survive recoverable interruptions after accepted media capture.

Minimum V1 persistence:

- owner
- intent
- media
- restaurant reference
- reaction
- caption
- visibility
- visit time
- state/timestamps as implemented.

If the current implementation rolls fields out in waves, incomplete fields must be explicit and must not be guessed from other behavior.

## 19. Restaurant reference states

Allowed:

### place

Resolved CRAVE place.

### candidate

User submitted a missing place; `candidate_id` exists and may resolve later.

### unresolved

Restaurant has not been identified yet.

Media remains valid in all three states.

## 20. Candidate promotion

When a candidate becomes a Place:

- resolve `candidate_id → place_id`;
- update the draft/contribution relationship;
- attach/upload using the resolved place contract;
- require no media recapture.

If blocked/rejected:

- retain recoverable draft state;
- explain truthfully;
- allow another restaurant selection or deletion where appropriate.

## 21. Upload states

Required user-facing semantics:

- saved locally
- queued/uploading
- uploaded/processing where useful
- failed/retry needed

Do not equate these with moderation or publication states.

Upload may continue after the composer exits when existing background/queue capability supports it.

## 22. Moderation states

Reuse/extend existing CRAVE moderation vocabulary.

Possible states include:

- approved
- pending review
- rejected

A moderation state must not render as transport failure.

Existing report/block primitives are reused rather than recreated as separate social systems.

## 23. Relationship to private logging

Private log is a first-class outcome, not a hidden privacy setting on a social post.

Private logs:

- may omit media;
- still may include restaurant/reaction/caption/time;
- remain private unless the user explicitly changes the contribution later through an approved flow;
- may contribute to private personalization only according to the Evidence/Privacy contracts.

## 24. Account/auth behavior

Stateful capture/draft ownership requires authentication under the current V1 implementation boundary.

If auth is missing at a stateful action:

- use the canonical auth gate;
- preserve resumable intent where supported;
- do not create anonymous durable media owned by an unknown account and later guess ownership.

Account A drafts never sync/publish as Account B.

## 25. Permission states

### Camera denied

Offer Library and permission retry where allowed.

### Camera permanently blocked

Offer Open Settings and Library.

### Microphone denied

Photo remains available. Video capture should explain what is unavailable rather than blocking the whole composer.

### Location denied

Restaurant Search remains available.

No background location permission is required.

## 26. Offline

Offline capture/logging must preserve durable local draft/media state.

If a contribution cannot fully commit while offline, explain `Saved on this device` / queued state rather than claiming publication.

No recoverable network failure should force recapture.

## 27. Stale / partial data

Missing menu data, stale restaurant metadata, or pending candidate verification must be represented as missing/uncertain evidence, not negative restaurant quality.

Examples:

- `Menu information unavailable`
- `Restaurant verification pending`

Do not fabricate operational truth to complete the composer.

## 28. Loading

Loading must be scoped to the operation:

- saving media locally;
- searching restaurants;
- creating candidate;
- committing;
- uploading/processing.

Do not blank the entire composer for background upload work when the user can continue safely.

## 29. Errors

Each error states:

1. what failed;
2. whether the draft/media is safe;
3. smallest valid next action.

Examples:

- Couldn't upload video — Retry
- Couldn't check restaurant yet — Try again later; draft is saved
- Local recording is no longer available — Replace media / Delete draft

Generic `Something went wrong, start over` is prohibited for recoverable states.

## 30. Draft recovery

When an unfinished draft exists, the composer may offer `Continue your draft`.

Do not nag, badge aggressively, or optimize re-engagement around unfinished posts.

Old abandoned draft cleanup requires an explicit lifecycle policy; recent saved media must not disappear silently.

## 31. Navigation / route migration

During migration:

- old `record-video/[placeId]` deep links remain valid;
- existing `add-spot` functionality remains reachable;
- legacy entry points hand off to composer only after parity;
- old routes are removed only after zero callers/deep links/tests remain.

The composer may be implemented as one route with internal steps/sheets. PM identifiers describe required product states, not mandatory route files.

## 32. Data reads

Potential reads include:

- auth identity;
- draft store;
- contextual place source;
- nearby place search;
- restaurant Search;
- candidate status;
- menu/dish data where trustworthy;
- moderation/transport state for recovery.

## 33. Data writes

Potential writes include:

- durable local media/draft;
- DiscoveryCandidate submission;
- candidate reference update;
- media upload request/confirm;
- committed private log/post;
- explicit reaction;
- visibility;
- deletion/retry actions.

Writes must retain owner/idempotency boundaries.

## 34. Evidence semantics

Strong explicit evidence:

- Loved it / Good / Not for me;
- Rank action when eligible.

Factual/prospective/weak evidence remains separate:

- visit/log;
- save;
- media capture;
- caption;
- impression/click;
- upload.

Posting frequency, media beauty, or public reach must never become positive taste authority by default.

## 35. Accessibility

Required design behavior:

- controls meet minimum touch target;
- camera actions have labels/roles;
- recording state has non-color cue;
- Photo/Video selection is screen-reader understandable;
- visibility consequence is text;
- reduced motion supported;
- large text reflows without hiding commit/privacy controls;
- error and success changes announce appropriately;
- no swipe-only required action;
- manual/library fallback exists where sensory/permission constraints make camera unusable.

Runtime VoiceOver/Dynamic Type/touch-target verification occurs after implementation and must not be claimed from this contract alone.

## 36. Analytics

Allowed analytics measure successful task completion and reliability, not engagement maximization.

Useful events:

- composer opened with source/intent;
- media accepted type/source;
- restaurant resolution path: place/candidate/unresolved;
- candidate submitted/resolved/blocked;
- commit intent/visibility class;
- upload/retry/failure category;
- draft recovery/deletion.

Do not optimize for:

- posts per day;
- time in composer;
- follower growth;
- media watch time;
- public reach;
- posting streaks.

Analytics must not silently reclassify private content as public/social evidence.

## 37. Responsive / platform behavior

Mobile native is the primary capture environment.

Web or unsupported camera environments must degrade to supported library/file selection and manual restaurant search where feasible rather than pretending native camera capability exists.

Safe-area and keyboard behavior must preserve final visibility/commit controls.

## 38. Visual rules

- dark-first CRAVE UI V2;
- food/media is the strongest visual element;
- interface recedes behind photography;
- one accent used sparingly for brand/selection/primary action;
- uncertainty/failure/privacy are not encoded only with the brand accent;
- no generic social-network engagement chrome;
- no star averages;
- no fake fit percentage;
- preview must show the actual selected media, not a generic `Photo selected` card as the permanent experience.

## 39. Prohibited behaviors

- losing accepted media because a restaurant does not yet exist in CRAVE;
- requiring `place_id` before durable capture;
- silently publishing after upload;
- silently defaulting public visibility;
- requiring location to post/log;
- forcing a written review;
- treating visit/media/caption as equivalent to Loved it;
- deleting legacy routes before parity/zero callers;
- building TikTok-style autoplay/creator mechanics;
- comments/reposts/public like counts as Posting V1 additions;
- fabricating dish/menu identity when capability is absent;
- blocking the entire composer on Dish Intelligence.

## 40. Current implementation mapping

### Already landed

PR #244:

- candidate status endpoint.

PR #245:

- `postingDraftStore.ts` durable local media;
- `restaurantRef: unresolved | candidate | place`;
- durable draft creation from `food-evidence`;
- `draftId` handoff to `add-spot`;
- candidate persistence and foreground/sign-in resolution.

These satisfy foundational portions of PMV2-01/02 but do not complete the full composer.

### Remaining primary implementation

- expand draft to full composer semantics;
- unified Photo | Video | Library capture surface;
- actual media preview;
- integrated restaurant/search/missing-place UX;
- reaction/caption/visibility/review;
- private-log and social-post commit endpoints/contracts;
- retry/recovery UI;
- moderation/privacy integration;
- legacy migration/retirement;
- runtime certification.

## 41. Readiness

**GREEN for bounded implementation against this contract.**

Named capability-gated behavior is allowed to omit itself honestly:

- Dish Intelligence suggestions;
- background/resumable upload capabilities beyond what the current platform supports;
- advanced media-quality/duplicate systems.

These are not permission to fabricate substitute semantics.

## 42. Acceptance criteria

The V1 Posting migration is not complete until all are true:

1. accepted photo and video are durable before restaurant resolution;
2. existing, candidate, and unresolved restaurant states do not lose media;
3. missing restaurant never requires recapture;
4. Photo/Video/Library are one composer experience;
5. preview shows real selected media;
6. location denial leaves manual Search usable;
7. public/connections media requirement is enforced;
8. private log can omit media;
9. visibility is explicit before public/social commit;
10. reaction evidence remains distinct from visit/media/caption;
11. upload/processing/moderation/publication states are distinguishable;
12. account-switch isolation is preserved;
13. app termination/offline recovery does not silently discard accepted media;
14. commit is idempotent/retry-safe;
15. legacy record-video/add-spot behavior remains compatible until zero callers are proven;
16. runtime accessibility/device/media tests pass before `FINAL` is claimed.
