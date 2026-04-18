import { create } from 'zustand';
import { User } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';

interface AuthStore {
  user: User | null;
  loading: boolean;
  init: () => void;
  signOut: () => Promise<void>;
}

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  loading: true,

  init: () => {
    // Hydrate from existing session
    supabase.auth.getSession().then(({ data }) => {
      set({ user: data.session?.user ?? null, loading: false });
    });

    // Listen for auth changes
    supabase.auth.onAuthStateChange((_event, session) => {
      set({ user: session?.user ?? null, loading: false });
    });
  },

  signOut: async () => {
    await supabase.auth.signOut();
    set({ user: null });
    // Clear persisted saves so the next user doesn't see them
    try {
      const { useHitlistStore } = await import('./hitlistStore');
      useHitlistStore.getState().clearSaves();
    } catch (err) {
      console.warn('[signOut] Failed to clear saves:', err);
    }
  },
}));
