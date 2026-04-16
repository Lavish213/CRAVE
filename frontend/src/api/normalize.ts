import { PlaceOut } from './places';
import { MenuItem } from './menu';
import { GeoJSONFeature } from './map';

export function normalizePlaceOut(raw: unknown): PlaceOut {
  const p = (raw ?? {}) as Record<string, unknown>;
  const firstImage = Array.isArray(p.images) && typeof p.images[0] === 'string' ? p.images[0] : null;
  const primaryImageUrl =
    (typeof p.primary_image_url === 'string' ? p.primary_image_url : null) ||
    (typeof p.primary_image === 'string' ? p.primary_image : null) ||
    firstImage ||
    null;
  return {
    id: String(p.id ?? ''),
    name: String(p.name ?? 'Unknown'),
    city_id: String(p.city_id ?? ''),
    rank_score: typeof p.rank_score === 'number' ? p.rank_score : 0,
    category: typeof p.category === 'string' ? p.category : null,
    categories: Array.isArray(p.categories) ? (p.categories as string[]) : [],
    address: typeof p.address === 'string' ? p.address : null,
    lat: typeof p.lat === 'number' ? p.lat : null,
    lng: typeof p.lng === 'number' ? p.lng : null,
    primary_image_url: primaryImageUrl,
    images: Array.isArray(p.images) ? (p.images as string[]) : [],
    website: typeof p.website === 'string' ? p.website : null,
    grubhub_url: typeof p.grubhub_url === 'string' ? p.grubhub_url : null,
    has_menu: Boolean(p.has_menu),
    price_tier: typeof p.price_tier === 'number' ? p.price_tier : null,
  };
}

export function normalizePlaces(raw: unknown): PlaceOut[] {
  if (!Array.isArray(raw)) return [];
  return raw.map(normalizePlaceOut);
}

export function normalizeMenuItems(raw: unknown): MenuItem[] {
  const items = Array.isArray(raw)
    ? raw
    : Array.isArray((raw as Record<string, unknown>)?.items)
    ? ((raw as Record<string, unknown>).items as unknown[])
    : [];
  return items.map((item) => {
    const i = (item ?? {}) as Record<string, unknown>;
    return {
      id: String(i.id ?? Math.random().toString(36).slice(2)),
      name: String(i.name ?? ''),
      description: typeof i.description === 'string' ? i.description : null,
      price: typeof i.price === 'number' ? i.price : null,
      category: typeof i.category === 'string' ? i.category : null,
    };
  });
}

export function normalizeMapFeatures(raw: unknown): GeoJSONFeature[] {
  const features = Array.isArray(raw)
    ? raw
    : Array.isArray((raw as Record<string, unknown>)?.features)
    ? ((raw as Record<string, unknown>).features as unknown[])
    : [];
  return features.filter((f) => {
    const feat = f as Record<string, unknown>;
    const geo = feat?.geometry as Record<string, unknown> | null;
    const coords = geo?.coordinates;
    if (!Array.isArray(coords)) return false;
    const lng = coords[0];
    const lat = coords[1];
    return (
      typeof lng === 'number' &&
      typeof lat === 'number' &&
      isFinite(lng) &&
      isFinite(lat) &&
      lat >= -90 && lat <= 90 &&
      lng >= -180 && lng <= 180
    );
  }) as GeoJSONFeature[];
}
