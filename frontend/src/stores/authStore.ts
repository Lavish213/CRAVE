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
    // Local sign-out must not be blocked by the remote call failing (a
    // network blip here previously meant `set({ user: null })` never ran
    // at all, so tapping "Sign Out" with a flaky connection silently did
    // nothing — no error, no feedback, still signed in). The user wanting
    // to leave this device wins over successfully invalidating the
    // session server-side.
    try {
      await supabase.auth.signOut();
    } catch (err) {
      console.warn('[signOut] Remote sign-out failed, clearing local session anyway:', err);
    }
    set({ user: null });
    // Clear persisted saves so the next user doesn't see them
    try {
      const { useCravesStore } = await import('./cravesStore');
      useCravesStore.getState().clearSaves();
    } catch (err) {
      console.warn('[signOut] Failed to clear saves:', err);
    }
  },
}));
