import { renderHook, waitFor } from '@testing-library/react-native';
import { fetchRecommendations, PlaceOut } from '../api/places';
import { useAuthStore } from '../stores/authStore';
import { useRecommendations } from './useRecommendations';

jest.mock('../api/places', () => ({ fetchRecommendations: jest.fn() }));
jest.mock('../stores/authStore', () => ({ useAuthStore: jest.fn() }));

const mockedFetchRecommendations = fetchRecommendations as jest.MockedFunction<typeof fetchRecommendations>;
const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;

const PLACE = { id: 'place-1', name: 'Recommended Place' } as unknown as PlaceOut;

function setUser(user: { id: string } | null): void {
  mockedUseAuthStore.mockImplementation((selector: (state: { user: { id: string } | null }) => unknown) =>
    selector({ user }),
  );
}

describe('useRecommendations', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setUser({ id: 'user-1' });
    mockedFetchRecommendations.mockResolvedValue([PLACE]);
  });

  it('loads recommendations for an authenticated enabled consumer', async () => {
    const { result } = renderHook(() => useRecommendations());
    await waitFor(() => expect(result.current).toEqual([PLACE]));
    expect(mockedFetchRecommendations).toHaveBeenCalledTimes(1);
  });

  it('does no hidden network work when the consumer is disabled', async () => {
    const { result } = renderHook(() => useRecommendations(false));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(result.current).toEqual([]);
    expect(mockedFetchRecommendations).not.toHaveBeenCalled();
  });

  it('does not fetch while signed out', async () => {
    setUser(null);
    const { result } = renderHook(() => useRecommendations());
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(result.current).toEqual([]);
    expect(mockedFetchRecommendations).not.toHaveBeenCalled();
  });

  it('invalidates an in-flight response when disabled before it resolves', async () => {
    let resolveRequest: (places: PlaceOut[]) => void = () => {};
    mockedFetchRecommendations.mockImplementationOnce(
      () => new Promise((resolve) => { resolveRequest = resolve; }),
    );

    const { result, rerender } = renderHook(
      ({ enabled }: { enabled: boolean }) => useRecommendations(enabled),
      { initialProps: { enabled: true } },
    );
    expect(mockedFetchRecommendations).toHaveBeenCalledTimes(1);

    rerender({ enabled: false });
    resolveRequest([PLACE]);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(result.current).toEqual([]);
  });
});
