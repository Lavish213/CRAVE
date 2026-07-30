import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { fetchCities } from '../api/cities';

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
  clearCity: () => void;
  initCities: () => Promise<void>;
}

export const useCityStore = create<CityStore>()(
  persist(
    (set) => ({
      cities: [],
      selectedCity: null,
      setCities: (cities) => set({ cities }),
      selectCity: (city) => set({ selectedCity: city }),
      // "Near Me" — no city override, Feed/Map fall back to GPS.
      clearCity: () => set({ selectedCity: null }),
      initCities: async () => {
        try {
          const cities = await fetchCities();
          const sorted = [...cities].sort((a, b) => a.name.localeCompare(b.name));
          set({ cities: sorted });
          // No default city auto-selected — leaving selectedCity null lets
          // GPS drive Feed/Map for a first-time user, instead of silently
          // locking every new install to a hardcoded city forever.
        } catch {
          // keep existing state on failure
        }
      },
    }),
    {
      name: 'crave-city-store',
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (state) => ({ selectedCity: state.selectedCity }),
    },
  ),
);
