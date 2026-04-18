import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { PlaceOut } from '../api/places';
import { fetchSaves, createSave, deleteSave } from '../api/saves';

interface HitlistStore {
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

export const useHitlistStore = create<HitlistStore>()(
  persist(
    (set, get) => ({
      saves: [],
      loading: false,
      error: null,

      loadSaves: async (userId: string) => {
        set({ loading: true, error: null });
        try {
          const items = await fetchSaves(userId);
          if (__DEV__) console.log('[HITLIST_STORE] loadSaves', { count: items.length });
          set({ saves: items, loading: false });
        } catch (err: any) {
          const msg = err?.response?.status === 401
            ? 'auth_required'
            : 'Failed to load saves';
          if (__DEV__) console.log('[HITLIST_STORE] loadSaves_error', msg, err?.response?.status);
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
          if (__DEV__) console.log('[HITLIST_STORE] addSave_ok', place.id);
          return null;
        } catch (err: any) {
          // Rollback
          set({ saves: get().saves.filter((s) => s.id !== place.id) });
          const msg = "Couldn't save. Try again.";
          if (__DEV__) console.log('[HITLIST_STORE] addSave_error', err?.response?.status, err?.message);
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
          if (__DEV__) console.log('[HITLIST_STORE] removeSave_ok', placeId);
          return null;
        } catch (err: any) {
          // Rollback
          set({ saves: prev });
          const msg = "Couldn't remove. Try again.";
          if (__DEV__) console.log('[HITLIST_STORE] removeSave_error', err?.response?.status, err?.message);
          return msg;
        }
      },

      clearSaves: () => {
        if (__DEV__) console.log('[HITLIST_STORE] clearSaves');
        set({ saves: [], error: null });
      },

      isSaved: (placeId: string) => get().saves.some((s) => s.id === placeId),
    }),
    {
      name: 'crave-hitlist',
      storage: createJSONStorage(() => AsyncStorage),
      // Only persist the saves array. loading/error are transient.
      partialize: (state) => ({ saves: state.saves }),
    },
  ),
);
