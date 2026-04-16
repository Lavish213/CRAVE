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
  initCities: () => Promise<void>;
}

export const useCityStore = create<CityStore>()(
  persist(
    (set, get) => ({
      cities: [],
      selectedCity: null,
      setCities: (cities) => set({ cities }),
      selectCity: (city) => set({ selectedCity: city }),
      initCities: async () => {
        try {
          const cities = await fetchCities();
          const sorted = [...cities].sort((a, b) => a.name.localeCompare(b.name));
          set({ cities: sorted });
          if (!get().selectedCity && sorted.length > 0) {
            const sf = sorted.find((c) => c.slug === 'san-francisco') ?? sorted[0];
            set({ selectedCity: sf });
          }
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
