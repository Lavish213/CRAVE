import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { PlaceOut } from '../api/places';

interface HitlistStore {
  saves: PlaceOut[];
  addSave: (place: PlaceOut) => void;
  removeSave: (placeId: string) => void;
  isSaved: (placeId: string) => boolean;
}

export const useHitlistStore = create<HitlistStore>()(
  persist(
    (set, get) => ({
      saves: [],
      addSave: (place) =>
        set((state) => ({
          saves: state.saves.find((s) => s.id === place.id)
            ? state.saves
            : [place, ...state.saves],
        })),
      removeSave: (placeId) =>
        set((state) => ({ saves: state.saves.filter((s) => s.id !== placeId) })),
      isSaved: (placeId) => get().saves.some((s) => s.id === placeId),
    }),
    {
      name: 'crave-hitlist',
      storage: createJSONStorage(() => AsyncStorage),
    },
  ),
);
