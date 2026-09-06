/**
 * useLocation.ts
 *
 * Location as an explicit lifecycle, not a collapsed `UserLocation | null`.
 * The old public contract folded three genuinely different situations --
 * "still resolving," "permission denied," and "permission granted but the
 * GPS read itself failed" -- into the same `null`, so no consumer could
 * ever tell them apart.
 *
 * The shared location is intentionally a fast, balanced-accuracy location
 * suitable for Feed/Search/Map startup. Add Spot already performs its own
 * fresh high-accuracy read because asserting a physical place has a stricter
 * accuracy requirement than discovery. The shared cache is refreshed after
 * five minutes when the app returns to the foreground, and foreground also
 * re-validates permission so coordinates revoked in OS Settings cannot stay
 * trusted until a full restart.
 */
import { useEffect, useState } from 'react';
import { AppState } from 'react-native';
import * as Location from 'expo-location';

export interface UserLocation {
  lat: number;
  lng: number;
}

export type LocationStatus =
  | 'resolving'
  | 'granted'
  | 'denied'
  | 'unavailable';

export interface LocationState {
  status: LocationStatus;
  coords: UserLocation | null;
  /** Epoch ms of the last successful coordinate read. */
  updatedAt: number | null;
}

/**
 * Feed/Search/Map may reuse balanced-accuracy coordinates for this long.
 * Add Spot intentionally bypasses this cache and requests a fresh,
 * high-accuracy location in its own transaction.
 */
export const LOCATION_FRESHNESS_MS = 5 * 60 * 1000;

const RESOLVING: LocationState = { status: 'resolving', coords: null, updatedAt: null };

let _state: LocationState | undefined;
let _promise: Promise<LocationState> | null = null;
const _listeners = new Set<(state: LocationState) => void>();

function _notifyListeners(state: LocationState): void {
  _listeners.forEach((listener) => listener(state));
}

function _setState(state: LocationState): LocationState {
  _state = state;
  _notifyListeners(state);
  return state;
}

async function readCurrentPosition(): Promise<LocationState> {
  try {
    const pos = await Location.getCurrentPositionAsync({
      accuracy: Location.Accuracy.Balanced,
    });
    return _setState({
      status: 'granted',
      coords: { lat: pos.coords.latitude, lng: pos.coords.longitude },
      updatedAt: Date.now(),
    });
  } catch {
    return _setState({ status: 'unavailable', coords: null, updatedAt: null });
  }
}

async function fetchLocation(): Promise<LocationState> {
  if (_state !== undefined) return _state;
  if (_promise) return _promise;

  _promise = (async () => {
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        return _setState({ status: 'denied', coords: null, updatedAt: null });
      }
      return readCurrentPosition();
    } catch {
      return _setState({ status: 'denied', coords: null, updatedAt: null });
    } finally {
      _promise = null;
    }
  })();

  return _promise;
}

/**
 * Re-validates permission on foreground and refreshes stale coordinates.
 *
 * This deliberately skips while the first request is still unresolved: the
 * OS permission sheet itself can generate a background/foreground transition,
 * and restarting the request there would create two competing permission/GPS
 * transactions. Once settled, foreground checks are non-prompting.
 */
async function recheckOnForeground(): Promise<void> {
  if (_state === undefined || _promise) return;

  let permissionStatus: string;
  try {
    ({ status: permissionStatus } = await Location.getForegroundPermissionsAsync());
  } catch {
    return;
  }

  if (permissionStatus !== 'granted') {
    if (_state.status !== 'denied' || _state.coords !== null) {
      _setState({ status: 'denied', coords: null, updatedAt: null });
    }
    return;
  }

  const now = Date.now();
  const isFreshGranted =
    _state.status === 'granted' &&
    _state.updatedAt !== null &&
    now - _state.updatedAt < LOCATION_FRESHNESS_MS;

  if (isFreshGranted) return;

  // Permission is granted and either the previous state was denied/
  // unavailable or its coordinates are stale. A direct position read avoids
  // needlessly invoking the permission-request API again after Settings.
  _promise = readCurrentPosition().finally(() => {
    _promise = null;
  });
  await _promise;
}

AppState.addEventListener('change', (state) => {
  if (state !== 'active') return;
  recheckOnForeground().catch(() => {});
});

export function _resetLocationStateForTests(): void {
  _state = undefined;
  _promise = null;
  _listeners.clear();
}

export function useLocationStatus(): LocationState {
  const [state, setState] = useState<LocationState>(_state ?? RESOLVING);

  useEffect(() => {
    _listeners.add(setState);

    if (_state !== undefined) {
      setState(_state);
    } else {
      fetchLocation().then(setState);
    }

    return () => {
      _listeners.delete(setState);
    };
  }, []);

  return state;
}

/**
 * Coordinates-or-null compatibility wrapper. Consumers that need to explain
 * resolving/denied/unavailable states should use useLocationStatus().
 */
export function useLocation(): UserLocation | null {
  return useLocationStatus().coords;
}
