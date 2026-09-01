// Coverage for FilterSheet's E8 category grouping -- categories now
// render under type-labeled sections instead of one flat "CUISINE" list
// that used to hide every dietary/ownership/occasion/recognition
// category behind a blacklist. See
// docs/CATEGORY_TAXONOMY_DESIGN_2026-08-31.md, Option A.
import React from 'react';
import { render, waitFor } from '@testing-library/react-native';
import { FilterSheet, EMPTY_FILTERS } from './FilterSheet';
import { fetchCategories } from '../api/categories';
import { __resetCategoryTypeCacheForTests } from '../hooks/useCategoryTypes';

jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  notificationAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'light' },
  NotificationFeedbackType: { Success: 'success' },
}));
jest.mock('../api/categories', () => ({
  fetchCategories: jest.fn(),
}));

const mockedFetchCategories = fetchCategories as jest.Mock;

const ALL_CATEGORIES = [
  { id: '1', name: 'Italian', icon: null, color: null, type: 'cuisine' },
  { id: '2', name: 'Fine Dining', icon: null, color: null, type: 'venue' },
  { id: '3', name: 'Halal', icon: null, color: null, type: 'dietary' },
  { id: '4', name: 'Black Owned', icon: null, color: null, type: 'ownership' },
  { id: '5', name: 'Late Night', icon: null, color: null, type: 'occasion' },
  { id: '6', name: 'Michelin Rated', icon: null, color: null, type: 'recognition' },
];

function renderSheet(availableCategories: string[]) {
  return render(
    <FilterSheet
      visible
      onClose={jest.fn()}
      filters={EMPTY_FILTERS}
      onChange={jest.fn()}
      availableCategories={availableCategories}
    />,
  );
}

describe('FilterSheet — category grouping (E8)', () => {
  beforeEach(() => {
    mockedFetchCategories.mockReset();
    __resetCategoryTypeCacheForTests();
  });

  it('groups categories under their real type section', async () => {
    mockedFetchCategories.mockResolvedValue(ALL_CATEGORIES);
    const { findByText, getByText } = renderSheet(['Italian', 'Halal', 'Black Owned']);

    await findByText('CUISINE');
    expect(getByText('DIETARY')).toBeTruthy();
    expect(getByText('OWNERSHIP')).toBeTruthy();
    expect(getByText('Italian')).toBeTruthy();
    expect(getByText('Halal')).toBeTruthy();
    expect(getByText('Black Owned')).toBeTruthy();
  });

  it('does not use the "Values" framing for ownership -- a factual header only', async () => {
    mockedFetchCategories.mockResolvedValue(ALL_CATEGORIES);
    const { findByText, queryByText } = renderSheet(['Black Owned']);

    await findByText('OWNERSHIP');
    expect(queryByText('VALUES')).toBeNull();
  });

  it('separates venue from cuisine instead of mislabeling venue categories as CUISINE', async () => {
    mockedFetchCategories.mockResolvedValue(ALL_CATEGORIES);
    const { findByText, getByText } = renderSheet(['Fine Dining', 'Italian']);

    await findByText('VENUE');
    expect(getByText('CUISINE')).toBeTruthy();
  });

  it('never renders a section for a type with zero available categories', async () => {
    mockedFetchCategories.mockResolvedValue(ALL_CATEGORIES);
    const { findByText, queryByText } = renderSheet(['Italian']);

    await findByText('CUISINE');
    expect(queryByText('DIETARY')).toBeNull();
    expect(queryByText('OWNERSHIP')).toBeNull();
    expect(queryByText('OCCASION')).toBeNull();
    expect(queryByText('RECOGNITION')).toBeNull();
    expect(queryByText('VENUE')).toBeNull();
  });

  it('filters out void categories (Restaurant, Bar, etc.) regardless of type', async () => {
    mockedFetchCategories.mockResolvedValue([
      ...ALL_CATEGORIES,
      { id: '7', name: 'Restaurant', icon: null, color: null, type: 'venue' },
    ]);
    const { findByText, queryByText } = renderSheet(['Italian', 'Restaurant']);

    await findByText('CUISINE');
    expect(queryByText('Restaurant')).toBeNull();
  });

  it('falls back to an untitled bucket for a name the type lookup has not classified yet, instead of dropping it', async () => {
    mockedFetchCategories.mockResolvedValue(ALL_CATEGORIES);
    const { findByText } = renderSheet(['Some New Category']);

    expect(await findByText('Some New Category')).toBeTruthy();
  });

  it('previously-hidden former-specialty categories (Halal, Michelin Rated) now render instead of being blacklisted', async () => {
    mockedFetchCategories.mockResolvedValue(ALL_CATEGORIES);
    const { findByText } = renderSheet(['Halal', 'Michelin Rated', 'Late Night']);

    expect(await findByText('Halal')).toBeTruthy();
    expect(await findByText('Michelin Rated')).toBeTruthy();
    expect(await findByText('Late Night')).toBeTruthy();
  });
});
