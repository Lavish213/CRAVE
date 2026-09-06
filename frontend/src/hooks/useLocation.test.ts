// Regression coverage for a confirmed bug: a permission denial used to be
// cached as final for the rest of the app's session, with no way to
// recover even after the user granted location access from OS Settings
// and returned to the app. Fixed by re-checking (non-prompting) on every
// foreground transition, and pushing a fresh value out to every mounted
// useLocation() consumer via a small listener set.
//
// Deliberately does NOT use jest.resetModules() + dynamic require() (the
// pattern cravesStore.test.ts uses) -- that clears React itself out of the
// module registry too, and a hook rendered against a second React module
// instance than the one @testing-library/react-native's renderHook holds
// throws "invalid hook call". useLocation.ts exports a small test-only
// reset function instead, so module-level cache state can still be
// cleared between cases without re-requiring the module.
import { renderHook, waitFor } from '@testing-library/react-native';
import { AppState } from 'react-native';

import { useLocation, useLocationStatus, _resetLocationStateForTests } from './useLocation';

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
  // useLocation.ts registers its foreground listener once at module load
  // -- reused across every test in this file rather than re-registered.
  const call = (AppState.addEventListener as jest.Mock).mock.calls.find(
    ([event]: [string, unknown]) => event === 'change'
  );
  expect(call).toBeTruthy();
  const callback = call![1];
  callback('active');
}

describe('useLocation', () => {
  beforeEach(() => {
    _resetLocationStateForTests();
    Location.requestForegroundPermissionsAsync.mockReset();
    Location.getForegroundPermissionsAsync.mockReset();
    Location.getCurrentPositionAsync.mockReset();
  });

  it('resolves a granted location normally', async () => {
    Location.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
    Location.getCurrentPositionAsync.mockResolvedValue({
      coords: { latitude: 1, longitude: 2 },
    });

    const { result } = renderHook(() => useLocation());

    await waitFor(() => expect(result.current).toEqual({ lat: 1, lng: 2 }));
  });

  it('re-checks on app foreground after a prior denial, and updates the mounted consumer', async () => {
    Location.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'denied' });

    const { result } = renderHook(() => useLocation());
    await waitFor(() => expect(result.current).toBeNull());

    // User granted access from OS Settings and returned to the app.
    // getForegroundPermissionsAsync is the non-prompting check the
    // foreground listener itself uses; requestForegroundPermissionsAsync
    // is what the resulting fetchLocation() re-fetch calls internally
    // (harmless once already granted -- it won't re-prompt) -- both need
    // to reflect the new state.
    Location.getForegroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
    Location.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
    Location.getCurrentPositionAsync.mockResolvedValue({
      coords: { latitude: 10, longitude: 20 },
    });

    triggerAppForeground();

    await waitFor(() => expect(result.current).toEqual({ lat: 10, lng: 20 }));
  });

  it('leaves the cache alone when a foreground check finds permission still denied', async () => {
    Location.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'denied' });

    const { result } = renderHook(() => useLocation());
    await waitFor(() => expect(result.current).toBeNull());

    Location.getForegroundPermissionsAsync.mockResolvedValue({ status: 'denied' });

    triggerAppForeground();
    // Give any (incorrect) re-fetch a chance to run before asserting.
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(Location.getCurrentPositionAsync).not.toHaveBeenCalled();
    expect(result.current).toBeNull();
  });

  it('does not re-check permission on foreground when a location was already resolved', async () => {
    Location.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
    Location.getCurrentPositionAsync.mockResolvedValue({
      coords: { latitude: 1, longitude: 2 },
    });

    renderHook(() => useLocation());
    await waitFor(() => expect(Location.getCurrentPositionAsync).toHaveBeenCalledTimes(1));

    triggerAppForeground();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(Location.getForegroundPermissionsAsync).not.toHaveBeenCalled();
  });
});

describe('useLocationStatus', () => {
  beforeEach(() => {
    _resetLocationStateForTests();
    Location.requestForegroundPermissionsAsync.mockReset();
    Location.getForegroundPermissionsAsync.mockReset();
    Location.getCurrentPositionAsync.mockReset();
  });

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

  it('reports unavailable (not denied) when permission is granted but the GPS read fails', async () => {
    Location.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
    Location.getCurrentPositionAsync.mockRejectedValue(new Error('timeout'));

    const { result } = renderHook(() => useLocationStatus());
    await waitFor(() => expect(result.current.status).toBe('unavailable'));
    expect(result.current.coords).toBeNull();
  });

  it('recovers denied -> Settings -> granted -> foreground into granted with fresh coords', async () => {
    Location.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'denied' });

    const { result } = renderHook(() => useLocationStatus());
    await waitFor(() => expect(result.current.status).toBe('denied'));

    // User granted access from OS Settings and returned to the app.
    Location.getForegroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
    Location.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
    Location.getCurrentPositionAsync.mockResolvedValue({
      coords: { latitude: 10, longitude: 20 },
    });

    triggerAppForeground();

    await waitFor(() => expect(result.current.status).toBe('granted'));
    expect(result.current.coords).toEqual({ lat: 10, lng: 20 });
  });
});
