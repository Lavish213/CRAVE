import { create } from 'zustand';
import { User } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';
import { useCravesStore } from './cravesStore';

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
    // Clear persisted saves so the next user doesn't see them. Static
    // import (was a dynamic `await import(...)`) -- there's no circular
    // dependency between authStore and cravesStore to work around, and the
    // dynamic form silently threw under Jest's CJS transform
    // (ERR_VM_DYNAMIC_IMPORT_CALLBACK_MISSING_FLAG), meaning the
    // clear-saves-on-signout behavior was never actually exercised by tests.
    try {
      useCravesStore.getState().clearSaves();
    } catch (err) {
      console.warn('[signOut] Failed to clear saves:', err);
    }
  },
}));
