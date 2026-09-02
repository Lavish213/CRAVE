# CRAVE Privacy Policy

**Last updated: August 25, 2026**

> **Before publishing**: this reflects CRAVE's actual features and data
> flows as of this writing (kept in sync with the in-app copy at
> `frontend/app/legal/privacy.tsx`), but it is not legal advice. Have an
> actual lawyer review it before it goes live at a public URL — App Store
> review and real users will both rely on it being accurate.

CRAVE ("we," "us," "our") operates the CRAVE mobile app. This policy
explains what information we collect, how we use it, and what choices
you have.

## Information We Collect

**Account information.** CRAVE uses Supabase for authentication. When you
create an account, we (through Supabase) store your email address and a
securely hashed password. We never see or store your plaintext password.

**Profile information.** Username, display name, bio, and profile photo,
if you choose to add them. Your profile is public by default (matching
how CRAVE's ranked-list/leaderboard features work), but you can make it
private in Settings.

**Location data.** With your permission, we use your device's location
to show nearby restaurants and improve search relevance. You can deny or
revoke this permission at any time in your device's system settings;
CRAVE remains usable without it, with reduced relevance in "nearby"
results.

**Content you submit.** Photos of places you upload, menu items you
submit or correct, restaurants you rank or save, comparisons you make
between places, and links you share (e.g. a TikTok or Instagram post
about a restaurant). This content may be shown to other users as part of
CRAVE's social features (ranked lists, "seen on social" style cards,
activity feed).

**Social graph.** Who you follow and who follows you, and who you've
blocked. Blocking is private — the person you block is not notified.

**Push notification token.** If you allow notifications, a device token
used only to tell you about your own uploads (e.g. a video was
approved).

**Device and usage data.** Basic technical information (app version, OS
version, crash reports) collected automatically to keep the app working
and to diagnose problems.

## How We Use Information

- To operate core features: showing restaurants, ranking your visits,
  building your feed, and displaying content you and others contribute.
- To improve search and discovery, including using your location for
  proximity ranking.
- To communicate with you about your account (e.g. security notices).
- To moderate content and enforce our Terms of Service.
- To fix bugs and improve reliability (crash/error reporting).

We do not sell your personal information.

## Third-Party Services

CRAVE relies on the following third parties to operate:

- **Supabase** — authentication and account credentials.
- **Cloudflare R2** — storage for the photos and videos you upload.
- **Railway** — hosts our backend and database.
- **Google Places API** — restaurant location, hours, and photo data
  used to populate CRAVE's catalog; we send place queries, not your
  personal account data.
- **DeepSeek** — used server-side to help extract menu information from
  restaurant websites. It does not receive your personal information;
  it only processes public webpage text to identify menu items.
- **Sentry** — crash and error monitoring, so we can detect and fix bugs.
- **Expo's push notification service** — delivers the notifications
  described above.

Each of these providers processes data under their own privacy policies
and only for the specific purpose CRAVE uses them for.

## Content Moderation

Photos and other content you or others submit may be reviewed for
policy violations (see Terms of Service). Reported content may be
hidden pending review. You can report content or block another user
directly in the app.

## Your Choices and Rights

- **Access/update**: edit your profile at any time in Settings.
- **Delete your account**: Settings → Delete Account permanently deletes
  your profile, your social graph (follows/blocks), and your login
  credentials (we ask Supabase to delete the underlying auth identity
  itself, not just the app profile, so you can't log back in with the
  same credentials afterward). This is irreversible and immediate. Your
  past public contributions — restaurant photos, menu submissions,
  rankings, moderation records — are not swept as part of this and may
  remain associated with the place or content itself rather than a
  reachable profile, the same way most social apps handle deleted
  accounts.
- **Location permission**: control via your device's system settings.
- **Blocking**: block any user from their profile; this also removes
  any existing follow relationship between you.

## Children's Privacy

CRAVE is not directed at children under 13 (or the relevant minimum age
in your jurisdiction), and we do not knowingly collect information from
children under that age.

## Data Security

We use industry-standard measures to protect your information, including
encrypted connections and access-controlled storage. No system is
perfectly secure, and we cannot guarantee absolute security.

## Changes to This Policy

We may update this policy from time to time. Material changes will be
reflected by updating the "Last updated" date above.

## Contact Us

Questions about this policy: **hello@crave.app**
