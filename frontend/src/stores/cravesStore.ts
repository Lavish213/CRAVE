// Renamed from hitlistStore.ts — "Hitlist" was never the app's actual name
// for this feature (the tab bar label was "Saves", and the internal name
// drifted informally). The whole tab — bookmarked places + shared links —
// is called Craves. See app/(tabs)/craves.tsx.
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { PlaceOut } from '../api/places';
import { fetchSaves, createSave, deleteSave } from '../api/saves';

interface CravesStore {
  saves: PlaceOut[];
  loading: boolean;
  error: string | null;

  // Load (or reload) saves from backend. Replaces local state.
  loadSaves: (userId: string) => Promise<void>;

  // Optimistic add — fires backend POST, rolls back on failure.
  // Returns error message string on failure, null on success.
  addSave: (place: PlaceOut, userId: string) => Promise<string | null>;

  // Optimistic remove — fires backend DELETE, rolls back on failure.
  // Returns error message string on failure, null on success.
  removeSave: (placeId: string, userId: string) => Promise<string | null>;

  // Clear all saves locally (call on sign-out).
  clearSaves: () => void;

  isSaved: (placeId: string) => boolean;
}

const _pendingSaves = new Set<string>();

// Previously every failure (network error, 500, 429, expired session) was
// collapsed into one of two hardcoded strings, so a user hitting the rate
// limiter (see backend app/core/rate_limit.py) saw the exact same message
// as a genuine server crash, and an expired/invalid session ('auth_required')
// was set but never actually checked by any screen — so a signed-in user
// with a stale token just saw an infinite "retry" loop with no way out.
function _classifyError(err: any, fallback: string): string {
  const status = err?.response?.status;
  if (status === 401) return 'auth_required';
  if (status === 429) return "You're doing that too fast — wait a moment and try again.";
  if (!err?.response) return "Can't reach CRAVE — check your connection.";
  return fallback;
}

export const useCravesStore = create<CravesStore>()(
  persist(
    (set, get) => ({
      saves: [],
      loading: false,
      error: null,

      loadSaves: async (userId: string) => {
        set({ loading: true, error: null });
        try {
          const items = await fetchSaves(userId);
          if (__DEV__) console.log('[CRAVES_STORE] loadSaves', { count: items.length });
          set({ saves: items, loading: false });
        } catch (err: any) {
          const msg = _classifyError(err, 'Failed to load saves');
          if (__DEV__) console.log('[CRAVES_STORE] loadSaves_error', msg, err?.response?.status);
          set({ loading: false, error: msg });
        }
      },

      addSave: async (place: PlaceOut, userId: string): Promise<string | null> => {
        // Guard: skip if already saved or a concurrent add is in flight
        const prev = get().saves;
        if (prev.find((s) => s.id === place.id) || _pendingSaves.has(place.id)) {
          return null;
        }
        _pendingSaves.add(place.id);
        // Optimistic: add immediately
        set({ saves: [place, ...prev] });
        try {
          await createSave(userId, place.id);
          if (__DEV__) console.log('[CRAVES_STORE] addSave_ok', place.id);
          return null;
        } catch (err: any) {
          // Rollback
          set({ saves: get().saves.filter((s) => s.id !== place.id) });
          const msg = _classifyError(err, "Couldn't save. Try again.");
          if (__DEV__) console.log('[CRAVES_STORE] addSave_error', err?.response?.status, err?.message);
          return msg;
        } finally {
          _pendingSaves.delete(place.id);
        }
      },

      removeSave: async (placeId: string, userId: string): Promise<string | null> => {
        // Optimistic: remove immediately
        const prev = get().saves;
        set({ saves: prev.filter((s) => s.id !== placeId) });
        try {
          await deleteSave(userId, placeId);
          if (__DEV__) console.log('[CRAVES_STORE] removeSave_ok', placeId);
          return null;
        } catch (err: any) {
          // Rollback
          set({ saves: prev });
          const msg = _classifyError(err, "Couldn't remove. Try again.");
          if (__DEV__) console.log('[CRAVES_STORE] removeSave_error', err?.response?.status, err?.message);
          return msg;
        }
      },

      clearSaves: () => {
        if (__DEV__) console.log('[CRAVES_STORE] clearSaves');
        set({ saves: [], error: null });
      },

      isSaved: (placeId: string) => get().saves.some((s) => s.id === placeId),
    }),
    {
      name: 'crave-saves',
      storage: createJSONStorage(() => AsyncStorage),
      // Only persist the saves array. loading/error are transient.
      partialize: (state) => ({ saves: state.saves }),
    },
  ),
);
