/**
 * useLocation.ts
 *
 * Location as an explicit lifecycle, not a collapsed `UserLocation | null`.
 * The old public contract folded three genuinely different situations --
 * "still resolving," "permission denied," and "permission granted but the
 * GPS read itself failed" -- into the same `null`, so no consumer could
 * ever tell them apart (a spinner, a permission prompt, and a "try again"
 * all need different UI, but all three read identically as "no location").
 * useLocationStatus() below exposes the real state; useLocation() stays a
 * thin, unchanged-signature wrapper around it for the existing call sites
 * that only ever wanted coordinates-or-null and don't branch on why.
 *
 * Caches the result for the session so multiple components share one
 * permission request / GPS call.
 */
import { useEffect, useState } from 'react';
import { AppState } from 'react-native';
import * as Location from 'expo-location';

export interface UserLocation {
  lat: number;
  lng: number;
}

export type LocationStatus =
  | 'resolving'     // permission/GPS request in flight (includes the very first call)
  | 'granted'       // usable coordinates available -- see `coords`
  | 'denied'        // permission denied; recoverable via OS Settings + foreground recheck
  | 'unavailable';  // permission granted but the position read itself failed (GPS off, no fix, timeout)

export interface LocationState {
  status: LocationStatus;
  coords: UserLocation | null; // non-null iff status === 'granted'
  /** epoch ms of the last successful coords read, for callers that want
   *  their own freshness policy. Null until the first 'granted'. */
  updatedAt: number | null;
}

const RESOLVING: LocationState = { status: 'resolving', coords: null, updatedAt: null };

// Module-level cache so multiple components share one permission request.
// `undefined` distinguishes "not yet resolved" from every settled state.
let _state: LocationState | undefined = undefined;
let _promise: Promise<LocationState> | null = null;

// Every mounted consumer registers here so a permission change discovered
// after the initial denial (see recheckIfPreviouslyDenied below) can push
// a fresh value to every already-mounted consumer, not just whichever
// component happens to remount next.
const _listeners = new Set<(state: LocationState) => void>();

function _notifyListeners(state: LocationState) {
  _listeners.forEach((listener) => listener(state));
}

async function fetchLocation(): Promise<LocationState> {
  if (_state !== undefined) return _state;
  if (_promise) return _promise;

  _promise = (async () => {
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        _state = { status: 'denied', coords: null, updatedAt: null };
        return _state;
      }

      try {
        const pos = await Location.getCurrentPositionAsync({
          accuracy: Location.Accuracy.Balanced,
        });
        _state = {
          status: 'granted',
          coords: { lat: pos.coords.latitude, lng: pos.coords.longitude },
          updatedAt: Date.now(),
        };
      } catch {
        // Permission granted, but the position read itself failed (GPS
        // off, no fix yet, hardware timeout) -- distinct from a denial:
        // sending this user to Settings would show a permission that's
        // already granted, telling them nothing useful.
        _state = { status: 'unavailable', coords: null, updatedAt: null };
      }
      return _state;
    } catch {
      // requestForegroundPermissionsAsync itself threw.
      _state = { status: 'denied', coords: null, updatedAt: null };
      return _state;
    }
  })();

  return _promise;
}

// A denial (or an unavailable read) used to be cached for the rest of the
// app's session with no way out: a user who denies the prompt on first
// launch, then later grants location access from OS Settings and returns
// to the app, would still see every location-dependent screen (map
// centering, Search's "nearest first", Home's location feed) behave as if
// still denied until a full app restart. Called on every foreground
// transition; already-granted state is left untouched
// (getForegroundPermissionsAsync() doesn't prompt, so this costs nothing
// when nothing has changed).
async function recheckIfPreviouslyDenied(): Promise<void> {
  // Skip while still resolving (undefined), not just when already
  // granted -- the permission dialog itself can trigger an AppState
  // background/foreground transition on some platforms while the very
  // first fetchLocation() call is still in flight. Without this, that
  // transition would wipe `_promise`/`_state` out from under the
  // original in-flight request and start a second, redundant one racing
  // it -- the same bug the old `_cached !== null` check (which also
  // covered `undefined`, by virtue of comparing against `null`
  // specifically) happened to avoid.
  if (_state === undefined || _state.status === 'granted') return;
  try {
    const { status } = await Location.getForegroundPermissionsAsync();
    if (status !== 'granted') return;
  } catch {
    return;
  }
  _state = undefined;
  _promise = null;
  const state = await fetchLocation();
  _notifyListeners(state);
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
  _state = undefined;
  _promise = null;
  _listeners.clear();
}

/** The full lifecycle: which state, plus coordinates when granted. */
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
 * Coordinates-or-null. Unchanged signature for the existing call sites
 * (Search/Feed/Map/Place Detail/ShareLinkSheet) that only ever wanted
 * "do I have a usable location right now" and don't need to distinguish
 * why not -- screens that do (e.g. a permanently-denied permission sheet)
 * should use useLocationStatus() instead.
 */
export function useLocation(): UserLocation | null {
  return useLocationStatus().coords;
}
