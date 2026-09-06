import { renderHook, waitFor } from '@testing-library/react-native';
import { AppState } from 'react-native';

import {
  LOCATION_FRESHNESS_MS,
  useLocation,
  useLocationStatus,
  _resetLocationStateForTests,
} from './useLocation';

jest.mock('expo-location', () => ({
  __esModule: true,
  requestForegroundPermissionsAsync: jest.fn(),
  getForegroundPermissionsAsync: jest.fn(),
  getCurrentPositionAsync: jest.fn(),
  Accuracy: { Balanced: 3 },
}));

const Location = jest.requireMock('expo-location') as {
  requestForegroundPermissionsAsync: jest.Mock;
  getForegroundPermissionsAsync: jest.Mock;
  getCurrentPositionAsync: jest.Mock;
};

function triggerAppForeground() {
  const call = (AppState.addEventListener as jest.Mock).mock.calls.find(
    ([event]: [string, unknown]) => event === 'change',
  );
  expect(call).toBeTruthy();
  const callback = call![1];
  callback('active');
}

function resetMocks() {
  _resetLocationStateForTests();
  Location.requestForegroundPermissionsAsync.mockReset();
  Location.getForegroundPermissionsAsync.mockReset();
  Location.getCurrentPositionAsync.mockReset();
}

describe('useLocation', () => {
  beforeEach(resetMocks);

  it('resolves a granted location normally', async () => {
    Location.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
    Location.getCurrentPositionAsync.mockResolvedValue({
      coords: { latitude: 1, longitude: 2 },
    });

    const { result } = renderHook(() => useLocation());

    await waitFor(() => expect(result.current).toEqual({ lat: 1, lng: 2 }));
  });

  it('re-checks on app foreground after a prior denial and updates the mounted consumer', async () => {
    Location.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'denied' });

    const { result } = renderHook(() => useLocation());
    await waitFor(() => expect(result.current).toBeNull());

    Location.getForegroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
    Location.getCurrentPositionAsync.mockResolvedValue({
      coords: { latitude: 10, longitude: 20 },
    });

    triggerAppForeground();

    await waitFor(() => expect(result.current).toEqual({ lat: 10, lng: 20 }));
  });

  it('leaves a denied state alone when the foreground permission is still denied', async () => {
    Location.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'denied' });

    const { result } = renderHook(() => useLocation());
    await waitFor(() => expect(result.current).toBeNull());

    Location.getForegroundPermissionsAsync.mockResolvedValue({ status: 'denied' });
    triggerAppForeground();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(Location.getCurrentPositionAsync).not.toHaveBeenCalled();
    expect(result.current).toBeNull();
  });

  it('re-validates permission on foreground without refreshing still-fresh coordinates', async () => {
    Location.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
    Location.getCurrentPositionAsync.mockResolvedValue({
      coords: { latitude: 1, longitude: 2 },
    });

    renderHook(() => useLocation());
    await waitFor(() => expect(Location.getCurrentPositionAsync).toHaveBeenCalledTimes(1));

    Location.getForegroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
    triggerAppForeground();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(Location.getForegroundPermissionsAsync).toHaveBeenCalledTimes(1);
    expect(Location.getCurrentPositionAsync).toHaveBeenCalledTimes(1);
  });
});

describe('useLocationStatus', () => {
  beforeEach(resetMocks);

  it('starts resolving, then reports granted with coords and a freshness timestamp', async () => {
    Location.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
    Location.getCurrentPositionAsync.mockResolvedValue({
      coords: { latitude: 1, longitude: 2 },
    });

    const { result } = renderHook(() => useLocationStatus());
    expect(result.current.status).toBe('resolving');
    expect(result.current.coords).toBeNull();

    await waitFor(() => expect(result.current.status).toBe('granted'));
    expect(result.current.coords).toEqual({ lat: 1, lng: 2 });
    expect(result.current.updatedAt).toEqual(expect.any(Number));
  });

  it('reports denied distinctly from unavailable', async () => {
    Location.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'denied' });

    const { result } = renderHook(() => useLocationStatus());
    await waitFor(() => expect(result.current.status).toBe('denied'));
    expect(result.current.coords).toBeNull();
  });

  it('reports unavailable when permission is granted but the GPS read fails', async () => {
    Location.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
    Location.getCurrentPositionAsync.mockRejectedValue(new Error('timeout'));

    const { result } = renderHook(() => useLocationStatus());
    await waitFor(() => expect(result.current.status).toBe('unavailable'));
    expect(result.current.coords).toBeNull();
  });

  it('does not restart an in-flight initial request on a foreground transition', async () => {
    let resolvePermission: (v: { status: string }) => void;
    Location.requestForegroundPermissionsAsync.mockImplementationOnce(
      () => new Promise((resolve) => { resolvePermission = resolve; }),
    );

    const { result } = renderHook(() => useLocationStatus());
    expect(result.current.status).toBe('resolving');

    triggerAppForeground();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(Location.requestForegroundPermissionsAsync).toHaveBeenCalledTimes(1);
    expect(Location.getForegroundPermissionsAsync).not.toHaveBeenCalled();

    Location.getCurrentPositionAsync.mockResolvedValue({
      coords: { latitude: 5, longitude: 6 },
    });
    resolvePermission!({ status: 'granted' });

    await waitFor(() => expect(result.current.status).toBe('granted'));
    expect(result.current.coords).toEqual({ lat: 5, lng: 6 });
  });

  it('recovers denied -> Settings -> granted -> foreground into fresh coordinates', async () => {
    Location.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'denied' });

    const { result } = renderHook(() => useLocationStatus());
    await waitFor(() => expect(result.current.status).toBe('denied'));

    Location.getForegroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
    Location.getCurrentPositionAsync.mockResolvedValue({
      coords: { latitude: 10, longitude: 20 },
    });

    triggerAppForeground();

    await waitFor(() => expect(result.current.status).toBe('granted'));
    expect(result.current.coords).toEqual({ lat: 10, lng: 20 });
  });

  it('refreshes stale granted coordinates when the app returns to foreground', async () => {
    const nowSpy = jest.spyOn(Date, 'now');
    nowSpy.mockReturnValue(1_000_000);
    Location.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
    Location.getCurrentPositionAsync.mockResolvedValueOnce({
      coords: { latitude: 1, longitude: 2 },
    });

    const { result } = renderHook(() => useLocationStatus());
    await waitFor(() => expect(result.current.coords).toEqual({ lat: 1, lng: 2 }));

    nowSpy.mockReturnValue(1_000_000 + LOCATION_FRESHNESS_MS + 1);
    Location.getForegroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
    Location.getCurrentPositionAsync.mockResolvedValueOnce({
      coords: { latitude: 3, longitude: 4 },
    });

    triggerAppForeground();

    await waitFor(() => expect(result.current.coords).toEqual({ lat: 3, lng: 4 }));
    expect(Location.getCurrentPositionAsync).toHaveBeenCalledTimes(2);
    nowSpy.mockRestore();
  });

  it('drops cached coordinates when permission was revoked in OS Settings', async () => {
    Location.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
    Location.getCurrentPositionAsync.mockResolvedValue({
      coords: { latitude: 1, longitude: 2 },
    });

    const { result } = renderHook(() => useLocationStatus());
    await waitFor(() => expect(result.current.status).toBe('granted'));

    Location.getForegroundPermissionsAsync.mockResolvedValue({ status: 'denied' });
    triggerAppForeground();

    await waitFor(() => expect(result.current.status).toBe('denied'));
    expect(result.current.coords).toBeNull();
  });
});
