import { useEffect, useState } from 'react';
import { fetchCategories } from '../api/categories';

// Module-level cache, not react-query -- FilterSheet renders inside
// Feed/Search/Map, none of which wrap their tests in a QueryClientProvider,
// and adding that requirement broke every existing test that opens the
// filter sheet. This gives the same "fetch once, reuse everywhere" effect
// without a context dependency: the first mount kicks off the fetch and
// every other concurrent/later mount awaits the same in-flight promise.
let cachedNameToType: Map<string, string> | null = null;
let inFlight: Promise<Map<string, string>> | null = null;

// Test-only: jest.resetModules() breaks React's single-instance
// invariant for a hook (unlike a plain store module), so tests reset
// this cache explicitly between cases instead.
export function __resetCategoryTypeCacheForTests(): void {
  cachedNameToType = null;
  inFlight = null;
}

function loadTypeByName(): Promise<Map<string, string>> {
  if (cachedNameToType) return Promise.resolve(cachedNameToType);
  if (inFlight) return inFlight;
  inFlight = fetchCategories()
    .then((categories) => {
      const map = new Map<string, string>();
      for (const c of categories) {
        if (c.type) map.set(c.name.toLowerCase(), c.type);
      }
      cachedNameToType = map;
      return map;
    })
    .catch(() => {
      // A failed fetch (offline, backend down) degrades to "no types
      // known yet" -- FilterSheet's unclassified bucket already handles
      // that gracefully. Deliberately NOT cached: a genuine network
      // failure shouldn't permanently poison this for the rest of the
      // session the way a successful empty response would.
      return new Map<string, string>();
    })
    .finally(() => {
      inFlight = null;
    });
  return inFlight;
}

/** Category name (lowercase) -> type ('cuisine'/'venue'/'dietary'/
 * 'ownership'/'occasion'/'recognition'). Empty map until the first fetch
 * resolves -- callers should treat an empty/missing lookup as "not yet
 * known" and degrade gracefully (see FilterSheet's unclassified bucket),
 * not as "this category has no type." */
export function useCategoryTypes(): Map<string, string> {
  const [typeByName, setTypeByName] = useState<Map<string, string>>(
    () => cachedNameToType ?? new Map(),
  );

  useEffect(() => {
    if (cachedNameToType) return;
    let cancelled = false;
    loadTypeByName().then((map) => {
      if (!cancelled) setTypeByName(map);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return typeByName;
}
