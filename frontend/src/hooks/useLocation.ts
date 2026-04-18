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
import * as Location from 'expo-location';

export interface UserLocation {
  lat: number;
  lng: number;
}

// Module-level cache so multiple components share one permission request
let _cached: UserLocation | null | undefined = undefined; // undefined = not yet resolved
let _promise: Promise<UserLocation | null> | null = null;

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

export function useLocation(): UserLocation | null {
  // undefined = loading, null = denied/unavailable, object = location
  const [location, setLocation] = useState<UserLocation | null | undefined>(
    _cached !== undefined ? _cached : undefined
  );

  useEffect(() => {
    if (_cached !== undefined) {
      setLocation(_cached);
      return;
    }
    fetchLocation().then(setLocation);
  }, []);

  return location ?? null;
}
