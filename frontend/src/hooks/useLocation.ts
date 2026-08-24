/**
 * useLocation.ts
 *
 * Returns the user's current location as { lat, lng }, or null if:
 * - permission denied
 * - location unavailable
 *
 * Caches the result for the session so multiple components share
 * one permission request / GPS call.
 */
import { useEffect, useState } from 'react';
import { AppState } from 'react-native';
import * as Location from 'expo-location';

export interface UserLocation {
  lat: number;
  lng: number;
}

// Module-level cache so multiple components share one permission request
let _cached: UserLocation | null | undefined = undefined; // undefined = not yet resolved
let _promise: Promise<UserLocation | null> | null = null;

// Every mounted useLocation() call registers here so a permission change
// discovered after the initial denial (see recheckIfPreviouslyDenied
// below) can push a fresh value to every already-mounted consumer, not
// just whichever component happens to remount next.
const _listeners = new Set<(loc: UserLocation | null) => void>();

function _notifyListeners(loc: UserLocation | null) {
  _listeners.forEach((listener) => listener(loc));
}

async function fetchLocation(): Promise<UserLocation | null> {
  if (_cached !== undefined) return _cached;
  if (_promise) return _promise;

  _promise = (async () => {
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        _cached = null;
        return null;
      }

      const pos = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });

      _cached = { lat: pos.coords.latitude, lng: pos.coords.longitude };
      return _cached;
    } catch {
      // Permission denied at OS level, or location unavailable
      _cached = null;
      return null;
    }
  })();

  return _promise;
}

// A denial used to be cached for the rest of the app's session with no way
// out: a user who denies the prompt on first launch, then later grants
// location access from OS Settings and returns to the app, would still see
// every location-dependent screen (map centering, Search's "nearest
// first", Home's location feed) behave as if still denied until a full
// app restart. Called on every foreground transition; a genuinely-still-
// denied cache is left untouched (getForegroundPermissionsAsync() doesn't
// prompt, so this costs nothing when nothing has changed).
async function recheckIfPreviouslyDenied(): Promise<void> {
  if (_cached !== null) return;
  try {
    const { status } = await Location.getForegroundPermissionsAsync();
    if (status !== 'granted') return;
  } catch {
    return;
  }
  _cached = undefined;
  _promise = null;
  const loc = await fetchLocation();
  _notifyListeners(loc);
}

AppState.addEventListener('change', (state) => {
  if (state !== 'active') return;
  recheckIfPreviouslyDenied().catch(() => {});
});

// Test-only: resets module-level cache/listener state between test cases.
// Not used by app code -- production never needs to forget a resolved
// location mid-session, only tests re-running this module's singleton
// state across independent cases need a way to clear it.
export function _resetLocationStateForTests(): void {
  _cached = undefined;
  _promise = null;
  _listeners.clear();
}

export function useLocation(): UserLocation | null {
  // undefined = loading, null = denied/unavailable, object = location
  const [location, setLocation] = useState<UserLocation | null | undefined>(
    _cached !== undefined ? _cached : undefined
  );

  useEffect(() => {
    _listeners.add(setLocation);

    if (_cached !== undefined) {
      setLocation(_cached);
    } else {
      fetchLocation().then(setLocation);
    }

    return () => {
      _listeners.delete(setLocation);
    };
  }, []);

  return location ?? null;
}
