# Cloudflare R2 production configuration runbook

Permanent runbook. Confirms the production R2 bucket is real,
reachable, and that a real upload/read/delete cycle works end-to-end
— not just that the credentials are present.

## Why this exists

`backend/app/services/upload/r2_client.py` reads `R2_ACCOUNT_ID`,
`R2_ACCESS_KEY`, `R2_SECRET_KEY`, `R2_BUCKET` from the environment with
no fallback literal (confirmed in the credential-leakage audit), builds
the S3-compatible endpoint as
`https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com`, and separately
reads `R2_PUBLIC_BASE_URL` for the bucket's actual public-serving
domain — deliberately *not* derived from the S3 endpoint, since that
host always requires SigV4-signed requests regardless of the bucket's
public-access setting (a URL built from it can never be loaded
directly by a client; this was a real, previously-fixed bug per the
file's own comment).

A wrong `R2_BUCKET` or `R2_PUBLIC_BASE_URL` doesn't necessarily error
— it can silently write to/read from the wrong bucket, or generate
public URLs that 403/404 for real users even though the upload
"succeeded" from the backend's point of view.

## Prerequisites

- Access to the Cloudflare dashboard (R2 section) for the production
  account.
- Access to Railway (backend env vars).

## Proof 1 — credentials and bucket identity are correct

- Cloudflare dashboard → R2 → confirm the production bucket name
  matches `R2_BUCKET`, and note its Account ID matches `R2_ACCOUNT_ID`.
- Confirm `R2_ACCESS_KEY`/`R2_SECRET_KEY` belong to an API token scoped
  to this bucket (Cloudflare → R2 → Manage API Tokens), not a token
  also used by a dev/staging bucket (a shared token isn't a security
  bug by itself, but makes "which environment does this key actually
  reach" unverifiable from the token alone).

**Pass:** account ID, bucket name, and token scope all confirmed
against the production bucket specifically.
**Fail:** correct the mismatched value; if the API token itself needs
to be scoped down, generate a new one and update Railway.

## Proof 2 — the public-serving URL actually resolves

- Cloudflare dashboard → R2 → the production bucket → Settings →
  confirm either a "Public Development URL" (`https://pub-<hash>.r2.dev`)
  is enabled, or a custom domain is mapped to the bucket.
- Confirm `R2_PUBLIC_BASE_URL` matches whichever of those is actually
  configured.

```bash
curl -sI "$R2_PUBLIC_BASE_URL/<a-known-existing-object-key>"
```

**Pass:** HTTP 200 (or 304), not 403/404.
**Fail:** `R2_PUBLIC_BASE_URL` doesn't match the bucket's actual public
config, or the bucket's public access isn't enabled at all — fix
whichever is wrong in the Cloudflare dashboard or the Railway env var.

## Proof 3 — a real upload/read/delete round-trip succeeds

Using the app itself (or `GET /api/v1/debug/version` to confirm you're
hitting the right deployment first): upload a real photo or video
through the normal in-app flow against production, then:

- Confirm the object appears in the Cloudflare dashboard's bucket
  browser under the expected key.
- Confirm `R2_PUBLIC_BASE_URL` + the returned key loads the image/video
  in a browser.
- Delete the place/video/photo through the app's normal deletion path
  (or account deletion, which also deletes R2 objects per Phase 7) and
  confirm the object is actually gone from the bucket, not orphaned.

**Pass:** all three steps succeed against the real production bucket.
**Fail:** narrow down which step failed — upload failure points back
to Proof 1 (credentials/permissions), read failure points back to
Proof 2 (public URL config), delete failure is a backend logic
question (re-check `account_deletion_service.py`'s R2-deletion path
and any per-object delete endpoint) rather than an R2 config issue.

## After running this

Record the result: append a dated Result section to this file, and
update `docs/MASTER_RELEASE_CERTIFICATION_MATRIX.md`'s Section 4.3
status.
