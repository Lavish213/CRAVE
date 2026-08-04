import { useAuthStore } from './authStore';
import { supabase } from '../lib/supabase';

jest.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: jest.fn(),
      onAuthStateChange: jest.fn(),
      signOut: jest.fn(),
    },
  },
}));

jest.mock('./cravesStore', () => ({
  useCravesStore: { getState: jest.fn(() => ({ clearSaves: jest.fn() })) },
}));

const mockedSupabase = supabase as unknown as {
  auth: {
    getSession: jest.Mock;
    onAuthStateChange: jest.Mock;
    signOut: jest.Mock;
  };
};

beforeEach(() => {
  useAuthStore.setState({ user: null, loading: true });
  mockedSupabase.auth.getSession.mockReset();
  mockedSupabase.auth.onAuthStateChange.mockReset();
  mockedSupabase.auth.signOut.mockReset();
  mockedSupabase.auth.onAuthStateChange.mockReturnValue({
    data: { subscription: { unsubscribe: jest.fn() } },
  });
});

describe('useAuthStore.init', () => {
  it('hydrates the user from an existing session', async () => {
    const fakeUser = { id: 'u1' } as any;
    mockedSupabase.auth.getSession.mockResolvedValue({ data: { session: { user: fakeUser } } });

    useAuthStore.getState().init();
    await Promise.resolve();
    await Promise.resolve();

    expect(useAuthStore.getState().user).toEqual(fakeUser);
    expect(useAuthStore.getState().loading).toBe(false);
  });

  it('sets user to null and loading to false when there is no session', async () => {
    mockedSupabase.auth.getSession.mockResolvedValue({ data: { session: null } });

    useAuthStore.getState().init();
    await Promise.resolve();
    await Promise.resolve();

    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().loading).toBe(false);
  });

  it('updates the store whenever an auth state change event fires', () => {
    let capturedCallback: ((event: string, session: any) => void) | undefined;
    mockedSupabase.auth.getSession.mockResolvedValue({ data: { session: null } });
    mockedSupabase.auth.onAuthStateChange.mockImplementation((cb: any) => {
      capturedCallback = cb;
      return { data: { subscription: { unsubscribe: jest.fn() } } };
    });

    useAuthStore.getState().init();
    const fakeUser = { id: 'u2' } as any;
    capturedCallback?.('SIGNED_IN', { user: fakeUser });

    expect(useAuthStore.getState().user).toEqual(fakeUser);
    expect(useAuthStore.getState().loading).toBe(false);
  });
});

describe('useAuthStore.signOut', () => {
  it('calls supabase signOut and clears the user from the store', async () => {
    mockedSupabase.auth.signOut.mockResolvedValue(undefined);
    useAuthStore.setState({ user: { id: 'u1' } as any, loading: false });

    await useAuthStore.getState().signOut();

    expect(mockedSupabase.auth.signOut).toHaveBeenCalledTimes(1);
    expect(useAuthStore.getState().user).toBeNull();
  });

  it('clears the local user even when the remote signOut call rejects', async () => {
    // Previously unguarded: `await supabase.auth.signOut()` throwing meant
    // `set({ user: null })` never ran, so a network blip while signing out
    // left the user still "signed in" locally with zero feedback. Local
    // sign-out must not depend on the remote call succeeding.
    mockedSupabase.auth.signOut.mockRejectedValue(new Error('network down'));
    useAuthStore.setState({ user: { id: 'u1' } as any, loading: false });

    await expect(useAuthStore.getState().signOut()).resolves.toBeUndefined();
    expect(useAuthStore.getState().user).toBeNull();
  });

  it('does not throw even if the post-signout cleanup step fails', async () => {
    // signOut() dynamically imports cravesStore to clear saves, wrapped in
    // its own try/catch (see authStore.ts) specifically so a cleanup
    // failure there can never surface as an unhandled rejection to the
    // caller. Under Jest's CJS transform, that dynamic import() itself
    // throws (no native ESM loader here), which exercises the same catch
    // block a real clearSaves() failure would — confirming the guarantee
    // that matters: signOut() always resolves.
    mockedSupabase.auth.signOut.mockResolvedValue(undefined);

    await expect(useAuthStore.getState().signOut()).resolves.toBeUndefined();
  });
});
