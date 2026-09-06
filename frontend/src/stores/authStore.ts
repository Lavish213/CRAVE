import { create } from 'zustand';
import { User } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';
import { queryClient } from '../lib/queryClient';
import { useCravesStore } from './cravesStore';
import { unregisterCurrentDevice } from '../services/pushNotifications';

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
    // Hard account-boundary cleanup for every React Query cache entry, not
    // just the handful whose keys are known to carry viewer-scoped data
    // (those are additionally keyed by user.id at the call site -- see
    // e.g. place/[id].tsx's ['myRankings', userId] -- because a query key
    // has to describe the data it contains regardless of this clear, for
    // the case where an account change happens while the query stays
    // mounted rather than remounting fresh). This clear alone would not
    // stop an in-flight request for the outgoing account from resolving
    // into a freshly-mounted screen for the incoming one; the per-key
    // scoping is what actually prevents that. Together: no viewer-scoped
    // response from Account A can ever be read back for Account B, on
    // this device, at any point.
    queryClient.clear();
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
    // Removes this device's push-token registration so a different
    // account signing into the same device afterward can't have a
    // moderation-outcome notification from *this* account's content
    // still land on it in the window before the next sign-in
    // re-registers. Already fully self-contained/non-throwing (see its
    // own docstring) -- no try/catch needed here.
    await unregisterCurrentDevice();
  },
}));
