// Search zero-state's "recent semantic searches" (Search Screen Contract
// §5/§6) — the user's own literal past queries, persisted locally. Not a
// server-side history or ranking signal; a query alone is never taste
// evidence (contract §12), and this store must stay that way.
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';

const MAX_RECENT_SEARCHES = 5;

interface RecentSearchesStore {
  queries: string[];
  addQuery: (query: string) => void;
  clear: () => void;
}

export const useRecentSearchesStore = create<RecentSearchesStore>()(
  persist(
    (set) => ({
      queries: [],
      addQuery: (query) => set((state) => {
        const trimmed = query.trim();
        if (!trimmed) return state;
        const deduped = [
          trimmed,
          ...state.queries.filter((existing) => existing.toLowerCase() !== trimmed.toLowerCase()),
        ];
        return { queries: deduped.slice(0, MAX_RECENT_SEARCHES) };
      }),
      clear: () => set({ queries: [] }),
    }),
    {
      name: 'crave-recent-searches-store',
      storage: createJSONStorage(() => AsyncStorage),
    },
  ),
);
