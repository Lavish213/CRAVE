import { create } from 'zustand';
import { PlaceOut } from '../api/places';
import { SearchInterpretation } from '../api/search';

export type SearchScope = 'all' | 'craves' | 'ranked';

interface SearchMapHandoff {
  query: string;
  searchSessionId: string;
  interpretation: SearchInterpretation;
  items: PlaceOut[];
  scope: SearchScope;
}

interface DiscoveryContextStore {
  searchMapHandoff: SearchMapHandoff | null;
  setSearchMapHandoff: (handoff: SearchMapHandoff) => void;
  clearSearchMapHandoff: () => void;
}

export const useDiscoveryContextStore = create<DiscoveryContextStore>((set) => ({
  searchMapHandoff: null,
  setSearchMapHandoff: (searchMapHandoff) => set({ searchMapHandoff }),
  clearSearchMapHandoff: () => set({ searchMapHandoff: null }),
}));
