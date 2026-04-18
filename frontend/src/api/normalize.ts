import { PlaceOut } from './places';
import { MenuItem } from './menu';
import { formatPrice } from '../utils/scoring';

const GENERIC_CATEGORIES = new Set(['restaurant', 'restaurants', 'bar', 'bars', 'other', 'others', '']);
// Truly meaningless — never show as category label
const VOID_CATEGORIES = new Set(['other', 'others', '']);

export interface NormalizedMapFeature {
  id: string;
  name: string;
  coordinate: { lat: number; lng: number };
  tier: 'elite' | 'trusted' | 'solid' | 'default';
  rank_score: number;
  price_tier: number | null;
  image: string | null;
  has_menu: boolean;
}

const API_BASE = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

function resolveImageUrl(url: unknown): string | null {
  if (!url || typeof url !== 'string') return null;
  if (url.startsWith('/api/image')) return `${API_BASE}${url}`;
  return url;
}

export function normalizePlaceOut(raw: unknown): PlaceOut {
  const p = (raw ?? {}) as Record<string, unknown>;
  const image =
    resolveImageUrl(p.primary_image_url) ||
    resolveImageUrl(p.primary_image) ||
    (Array.isArray(p.images) ? resolveImageUrl(p.images[0]) : null) ||
    null;
  const rawCategories = Array.isArray(p.categories) ? (p.categories as string[]) : [];
  const categories = rawCategories.filter((c) => !GENERIC_CATEGORIES.has((c ?? '').toLowerCase().trim()));

  function firstSpecific(cats: string[]): string | null {
    return cats.find((c) => !GENERIC_CATEGORIES.has((c ?? '').toLowerCase().trim())) ?? null;
  }

  function bestCategory(rawCat: string, cats: string[]): string | null {
    // Priority 1: backend-provided specific category (non-generic)
    if (rawCat && !GENERIC_CATEGORIES.has(rawCat.toLowerCase())) return rawCat;
    // Priority 2: first specific from categories list
    const specific = firstSpecific(cats);
    if (specific) return specific;
    // Priority 3: backend fallback (e.g. "Restaurant") — not void, not null
    if (rawCat && !VOID_CATEGORIES.has(rawCat.toLowerCase())) return rawCat;
    // Priority 4: first non-void from categories list
    const nonVoid = cats.find((c) => !VOID_CATEGORIES.has((c ?? '').toLowerCase().trim()));
    return nonVoid ?? null;
  }

  // Prefer singular field if it's specific, else derive from filtered categories
  const rawCategory = typeof p.category === 'string' ? p.category.trim() : '';
  const category = bestCategory(rawCategory, rawCategories);
  const rankScore = typeof p.rank_score === 'number' ? p.rank_score : 0;

  // Use backend-computed tier if present; derive locally as fallback
  const rawTier = p.tier as string | undefined;
  const tier: PlaceOut['tier'] = (
    rawTier === 'crave_pick' || rawTier === 'gem' || rawTier === 'solid' || rawTier === 'new'
      ? rawTier
      : rankScore >= 0.42 ? 'crave_pick'
      : rankScore >= 0.32 ? 'gem'
      : rankScore >= 0.22 ? 'solid'
      : 'new'
  );

  const normalized = {
    id: String(p.id ?? ''),
    name: String(p.name ?? 'Unknown'),
    city_id: String(p.city_id ?? ''),
    rank_score: rankScore,
    tier,
    distance_miles: typeof p.distance_miles === 'number' ? p.distance_miles : null,
    category,
    categories,
    address: typeof p.address === 'string' ? p.address : null,
    lat: typeof p.lat === 'number' ? p.lat : null,
    lng: typeof p.lng === 'number' ? p.lng : null,
    image,
    primary_image_url: image,
    images: Array.isArray(p.images) ? (p.images as string[]) : [],
    website: typeof p.website === 'string' ? p.website : null,
    grubhub_url: typeof p.grubhub_url === 'string' ? p.grubhub_url : null,
    has_menu: Boolean(p.has_menu),
    price_tier: typeof p.price_tier === 'number' ? p.price_tier : null,
    price: undefined as string | undefined,
  };
  // Populate formatted price after object is built so inferPrice can read it
  normalized.price = formatPrice(normalized) ?? undefined;
  if (__DEV__) {
    console.log('[NORMALIZE] place', normalized.id, normalized.name, {
      category: normalized.category,
      categories: normalized.categories,
      lat: normalized.lat,
      lng: normalized.lng,
      has_image: !!normalized.image,
    });
  }
  return normalized;
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

export function normalizeMapFeatures(raw: unknown): NormalizedMapFeature[] {
  const features = Array.isArray(raw)
    ? raw
    : Array.isArray((raw as Record<string, unknown>)?.features)
    ? ((raw as Record<string, unknown>).features as unknown[])
    : [];

  const result: NormalizedMapFeature[] = [];
  for (const f of features) {
    const feat = (f ?? {}) as Record<string, unknown>;
    const geo = feat.geometry as Record<string, unknown> | null;
    const coords = geo?.coordinates;
    if (!Array.isArray(coords)) continue;
    const lng = coords[0];
    const lat = coords[1];
    if (
      typeof lng !== 'number' ||
      typeof lat !== 'number' ||
      !isFinite(lng) ||
      !isFinite(lat) ||
      lat < -90 || lat > 90 ||
      lng < -180 || lng > 180
    ) continue;

    const props = (feat.properties ?? {}) as Record<string, unknown>;
    result.push({
      id: String(props.id ?? ''),
      name: String(props.name ?? ''),
      coordinate: { lat, lng },
      tier: (['elite', 'trusted', 'solid', 'default'].includes(props.tier as string)
        ? props.tier
        : 'default') as NormalizedMapFeature['tier'],
      rank_score: typeof props.rank_score === 'number' ? props.rank_score : 0,
      price_tier: typeof props.price_tier === 'number' ? props.price_tier : null,
      image:
        resolveImageUrl(props.primary_image_url) ||
        resolveImageUrl(props.primary_image) ||
        null,
      has_menu: Boolean(props.has_menu),
    });
  }
  return result;
}
