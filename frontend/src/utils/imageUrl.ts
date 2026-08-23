// Helpers for sizing backend-proxied place images.
//
// Place photos come back from the API as proxy URLs pointing at the
// backend's /api/v1/image route (see backend/app/api/v1/routes/image.py),
// which forwards to Google Places and accepts an optional `w` width param.
//
// That route now defaults to a thumbnail-sized 800px, because the feed
// renders many images at once and previously pulled full-size (1600px)
// source images for every one of them — several hundred KB to a few MB
// each, thrown away immediately by the card's crop. Surfaces that render
// a genuinely large image (the place-detail hero gallery, which is full
// screen width) should opt back up via `withImageWidth`.

/** Max width the backend proxy will honor — larger values are clamped there. */
export const MAX_IMAGE_WIDTH = 1600;

// Small round-avatar surfaces (leaderboard rows, activity feed rows) were
// still getting the proxy's 800px thumbnail default for a ~40pt image --
// several hundred KB fetched and decoded just to be shown at avatar size.
// 96 covers a 40pt avatar at up to 2.4x device pixel ratio.
export const AVATAR_IMAGE_WIDTH = 96;

/**
 * Return `url` with the backend image proxy's width param set to `width`.
 *
 * Leaves non-proxy URLs untouched: uploaded photos are served straight
 * from R2 and Google URLs may be stored directly on older rows, and
 * neither understands a `w` param — appending one would at best be
 * ignored and at worst break a signed URL's signature.
 */
export function withImageWidth(url: string | null | undefined, width: number): string | null {
  if (!url) return null;
  if (!url.includes('/api/v1/image')) return url;

  try {
    // Relative URLs are possible in principle; give the URL parser a base
    // it can discard so it doesn't throw on them.
    const parsed = new URL(url, 'http://placeholder.invalid');
    parsed.searchParams.set('w', String(width));
    return url.startsWith('http')
      ? parsed.toString()
      : `${parsed.pathname}${parsed.search}`;
  } catch {
    return url;
  }
}
