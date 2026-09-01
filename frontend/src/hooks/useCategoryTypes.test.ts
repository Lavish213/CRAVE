// Coverage for useCategoryTypes' module-level cache (E8 filter grouping).
// Deliberately not react-query -- FilterSheet renders inside Feed/Search/
// Map, none of which wrap their tests in a QueryClientProvider, so this
// hook has to manage its own fetch-once-and-share caching.
import { renderHook, waitFor } from '@testing-library/react-native';
import { useCategoryTypes, __resetCategoryTypeCacheForTests } from './useCategoryTypes';
import { fetchCategories } from '../api/categories';

jest.mock('../api/categories', () => ({
  fetchCategories: jest.fn(),
}));

const mockedFetchCategories = fetchCategories as jest.Mock;

describe('useCategoryTypes', () => {
  beforeEach(() => {
    mockedFetchCategories.mockReset();
    __resetCategoryTypeCacheForTests();
  });

  it('starts empty and populates once the fetch resolves', async () => {
    mockedFetchCategories.mockResolvedValue([
      { id: '1', name: 'Halal', icon: null, color: null, type: 'dietary' },
    ]);
    const { result } = renderHook(() => useCategoryTypes());

    expect(result.current.size).toBe(0);
    await waitFor(() => expect(result.current.get('halal')).toBe('dietary'));
  });

  it('lowercases names for lookup', async () => {
    mockedFetchCategories.mockResolvedValue([
      { id: '1', name: 'Michelin Rated', icon: null, color: null, type: 'recognition' },
    ]);
    const { result } = renderHook(() => useCategoryTypes());

    await waitFor(() => expect(result.current.get('michelin rated')).toBe('recognition'));
  });

  it('skips a category with a null type rather than mapping it to "null"', async () => {
    mockedFetchCategories.mockResolvedValue([
      { id: '1', name: 'Mystery', icon: null, color: null, type: null },
    ]);
    const { result } = renderHook(() => useCategoryTypes());

    await waitFor(() => expect(mockedFetchCategories).toHaveBeenCalled());
    expect(result.current.has('mystery')).toBe(false);
  });

  it('shares one fetch across concurrently-mounted instances', async () => {
    mockedFetchCategories.mockResolvedValue([
      { id: '1', name: 'Vegan', icon: null, color: null, type: 'dietary' },
    ]);
    const a = renderHook(() => useCategoryTypes());
    const b = renderHook(() => useCategoryTypes());

    await waitFor(() => expect(a.result.current.get('vegan')).toBe('dietary'));
    await waitFor(() => expect(b.result.current.get('vegan')).toBe('dietary'));
    expect(mockedFetchCategories).toHaveBeenCalledTimes(1);
  });

  it('degrades to an empty map on a failed fetch instead of throwing', async () => {
    mockedFetchCategories.mockRejectedValue(new Error('Network Error'));
    const { result } = renderHook(() => useCategoryTypes());

    await waitFor(() => expect(mockedFetchCategories).toHaveBeenCalled());
    expect(result.current.size).toBe(0);
  });

  it('reuses the cache across a second mount without refetching', async () => {
    mockedFetchCategories.mockResolvedValue([
      { id: '1', name: 'Vegan', icon: null, color: null, type: 'dietary' },
    ]);
    const first = renderHook(() => useCategoryTypes());
    await waitFor(() => expect(first.result.current.get('vegan')).toBe('dietary'));

    const second = renderHook(() => useCategoryTypes());
    expect(second.result.current.get('vegan')).toBe('dietary');
    expect(mockedFetchCategories).toHaveBeenCalledTimes(1);
  });
});
