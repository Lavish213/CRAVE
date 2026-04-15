// src/stores/cityStore.ts
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';

export interface City {
  id: string;
  name: string;
  slug: string | null;
  lat: number | null;
  lng: number | null;
}

interface CityStore {
  cities: City[];
  selectedCity: City | null;
  setCities: (cities: City[]) => void;
  selectCity: (city: City) => void;
}

export const useCityStore = create<CityStore>()(
  persist(
    (set) => ({
      cities: [],
      selectedCity: null,
      setCities: (cities) => set({ cities }),
      selectCity: (city) => set({ selectedCity: city }),
    }),
    {
      name: 'crave-city-store',
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (state) => ({ selectedCity: state.selectedCity }),
    },
  ),
);
