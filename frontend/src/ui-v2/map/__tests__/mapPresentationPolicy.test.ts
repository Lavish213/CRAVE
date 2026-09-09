import {
  DEFAULT_MAP_VISIBLE_PLACE_LIMIT,
  selectMapPresentationItems,
} from '../mapPresentationPolicy';

describe('selectMapPresentationItems', () => {
  const items = Array.from({ length: 15 }, (_, index) => ({ id: `place-${index + 1}` }));

  it('keeps small candidate sets intact', () => {
    expect(selectMapPresentationItems(items.slice(0, 4))).toEqual(items.slice(0, 4));
  });

  it('bounds default simultaneous place presentation without reordering', () => {
    expect(selectMapPresentationItems(items)).toEqual(items.slice(0, DEFAULT_MAP_VISIBLE_PLACE_LIMIT));
  });

  it('preserves a selected place outside the initial presentation window', () => {
    const result = selectMapPresentationItems(items, { maxVisible: 5, selectedId: 'place-12' });
    expect(result).toEqual([items[0], items[1], items[2], items[3], items[11]]);
  });

  it('does not invent a candidate when the selected id is absent', () => {
    expect(selectMapPresentationItems(items, { maxVisible: 3, selectedId: 'missing' })).toEqual(items.slice(0, 3));
  });
});
