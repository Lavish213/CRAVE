# Store metadata draft

First-pass copy for App Store Connect / Play Console, derived from
what CRAVE actually does (per this repo and
`docs/PROVIDER_DATA_FLOW_INVENTORY.md`), not aspirational marketing
claims. Treat as a draft to be reviewed by whoever owns the actual
store listings — names/claims here should be checked against
final legal/brand review before submission.

## App name

**CRAVE**

## Subtitle / short description (iOS subtitle, Play short description — 80 char limit)

"Rank, save, and discover real food spots — not a star average."

## Long description (draft)

CRAVE is a food discovery app built around one idea: a 5-star average
tells you nothing. CRAVE replaces it with head-to-head ranking — you
compare places you've actually visited against each other, and CRAVE
builds a personal, ordered list of your real favorites over time.

What you can do with CRAVE:
- **Discover** — a tiered feed (Crave Picks, Gems, Solid picks, and
  new spots) built from real ranking data, plus a live map of what's
  around you.
- **Rank** — after visiting a place, rank it head-to-head against
  places you've already ranked. No star ratings, no guessing what a
  "4" means.
- **Save & remember** — save places you want to try, track what
  you've visited, and keep notes.
- **Share the moment** — record and share a short food video, add
  photos, and see what friends are ranking.
- **Find your people** — follow friends, see a leaderboard, and check
  your own taste profile.

CRAVE does not sell your data. See our Privacy Policy for exactly what
we collect and why: [hosted privacy policy URL — pending Section 3.1].

## Category recommendation

Primary: **Food & Drink**. Secondary (if platform allows a second):
**Social Networking** or **Lifestyle** (CRAVE has real social features
— follow, friends feed, leaderboard — but food discovery is the
primary use case).

## Keywords (draft, iOS App Store keyword field)

food, restaurants, ranking, discovery, foodie, map, reviews, places to
eat, food video, dining

*(Verify current App Store keyword-field character limit and
comma-separation rules before final submission — these change
occasionally.)*

## Support / contact information

- **Support URL**: [pending — needs a real support page or contact
  form; do not leave this blank, both stores require it].
- **Support email**: [pending — a real monitored address, not a
  placeholder].
- **Copyright / developer identity**: confirm the legal entity name
  registered with both Apple Developer and Google Play Console matches
  whatever's named in the hosted Privacy Policy/Terms.

## Age / content rating

CRAVE contains user-generated content (photos, videos, text notes,
social features) with moderation/reporting (`ReportPhotoSheet`,
moderation routes in the backend) but no age-restricted content by
design (no alcohol-focused content beyond incidental restaurant/bar
listings, no mature themes). Recommended starting point: **4+ / Teen**
depending on each store's exact questionnaire wording for
"user-generated content with reporting" — complete the actual
questionnaire against current store wording rather than assuming this
draft's recommendation still matches (store questionnaires change).

## Review notes (for the App Review team)

- The app requires sign-in (Google or Apple) to use most features;
  reviewers should sign in to see the full experience — provide the
  "established account" from
  `docs/RELEASE_TEST_ACCOUNTS_AND_FIXTURES.md` as a demo account if
  either store's review process requests one.
- Camera/microphone/location permissions are used for: recording a
  short food video, and showing nearby places / biasing search by
  distance, respectively — matches the purpose strings already in
  `frontend/app.json` (verified accurate, matrix Section 8.1, PASS).
- Account deletion is available in-app (Settings → Delete Account) and
  via [the hosted deletion page — pending Section 3.2].

## UGC / moderation explanation (for store review, if asked)

CRAVE allows users to upload photos/videos of food and add text notes.
Users can report photos (`ReportPhotoSheet`) and block other users
(`user/[id].tsx`'s block flow). [Confirm current moderation-response
SLA/process with whoever owns backend moderation operations before
stating one to reviewers — not verified as part of this document.]

## Demo/test account requirements

If either store's review flow requires a demo account, use the
"established account" defined in
`docs/RELEASE_TEST_ACCOUNTS_AND_FIXTURES.md` (has real rankings,
saves, media, and follows — reviewers testing a brand-new account
would see mostly empty states, which don't represent the product well).

## What's explicitly not drafted here

Screenshots (see `docs/SCREENSHOT_CAPTURE_PLAN.md`), the actual Privacy
Policy/Data Safety declarations (see
`docs/PROVIDER_DATA_FLOW_INVENTORY.md` and matrix Section 8.2), and
final legal entity/copyright details (need explicit confirmation from
whoever holds the Apple/Google developer accounts, not assumed here).
