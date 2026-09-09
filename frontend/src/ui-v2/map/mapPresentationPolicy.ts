export interface MapPresentationItem {
  id: string;
}

export interface MapPresentationOptions {
  maxVisible?: number;
  selectedId?: string | null;
}

export const DEFAULT_MAP_VISIBLE_PLACE_LIMIT = 10;

/**
 * Bounds simultaneous individual place competition without changing the
 * underlying candidate universe or its ordering semantics.
 *
 * The selected place is preserved even when it falls outside the initial
 * window. Callers retain the complete candidate set for list parity,
 * Search-this-area, and subsequent viewport decisions.
 */
export function selectMapPresentationItems<T extends MapPresentationItem>(
  items: readonly T[],
  options: MapPresentationOptions = {},
): T[] {
  const maxVisible = Math.max(1, Math.floor(options.maxVisible ?? DEFAULT_MAP_VISIBLE_PLACE_LIMIT));
  if (items.length <= maxVisible) return [...items];

  const selectedId = options.selectedId ?? null;
  const initial = items.slice(0, maxVisible);
  if (!selectedId || initial.some((item) => item.id === selectedId)) return initial;

  const selected = items.find((item) => item.id === selectedId);
  if (!selected) return initial;

  return [...initial.slice(0, maxVisible - 1), selected];
}
