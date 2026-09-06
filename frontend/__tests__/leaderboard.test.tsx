// leaderboard.tsx — first dedicated coverage. Locks in: the
// global/friends scope toggle (including the no-op re-press guard), the
// scope-specific empty-state copy, medal-vs-plain-rank display, the
// label fallback chain, the "you" row (disabled, distinct style, no
// navigation), and the conditional handle line (only shown when both a
// display_name and username exist).
import React from 'react';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import LeaderboardScreen from '../app/leaderboard';
import { useAuthStore } from '../src/stores/authStore';
import { LeaderboardRow, fetchLeaderboard } from '../src/api/social';

const mockPush = jest.fn();
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useFocusEffect: (cb: () => void) => require('react').useEffect(cb, [cb]),
}));
jest.mock('../src/stores/authStore', () => ({
  useAuthStore: jest.fn(),
}));
jest.mock('../src/api/social', () => ({
  fetchLeaderboard: jest.fn(),
}));
jest.mock('expo-haptics', () => ({
  selectionAsync: jest.fn(),
}));
jest.mock('../src/components/AuthSheet', () => {
  const { Text } = require('react-native');
  return {
    AuthSheet: ({ visible }: { visible: boolean }) =>
      visible ? <Text testID="auth-sheet-visible">auth</Text> : null,
  };
});

const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;
const mockedFetchLeaderboard = fetchLeaderboard as jest.MockedFunction<typeof fetchLeaderboard>;

function setAuth(user: { id: string } | null) {
  mockedUseAuthStore.mockImplementation((selector: (s: unknown) => unknown) => selector({ user }));
}

function makeRow(overrides: Partial<LeaderboardRow> = {}): LeaderboardRow {
  return { user_id: 'u1', places_logged: 10, rank: 4, username: 'someone', display_name: 'Someone Name', avatar_url: null, ...overrides };
}

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <LeaderboardScreen />
      </QueryClientProvider>,
    ),
  };
}

describe('LeaderboardScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setAuth({ id: 'me' });
  });

  it('scopes the friends-board cache key to the signed-in user, but leaves the global board key unscoped (shared, not viewer-dependent)', async () => {
    // Key-shape assertion complementing queryClient.test.ts's real
    // cache-boundary integration test (which uses myRankings as the
    // primary case). Global deliberately does NOT carry user.id -- every
    // viewer sees the same board, so scoping it would just fragment one
    // shared cache entry into one per account for identical data (see
    // leaderboard.tsx's own comment on the queryKey).
    mockedFetchLeaderboard.mockResolvedValue([]);
    const { client, findByLabelText } = renderScreen();
    await findByLabelText('Global leaderboard');
    expect(client.getQueryData(['leaderboard', 'global', null])).toEqual([]);

    fireEvent.press(await findByLabelText('Friends leaderboard'));
    await waitFor(() => expect(client.getQueryData(['leaderboard', 'friends', 'me'])).toEqual([]));
  });

  it('fetches the global scope by default, and switches to friends on toggle (but not on a re-press of the active scope)', async () => {
    mockedFetchLeaderboard.mockResolvedValue([]);
    const { findByLabelText } = renderScreen();

    await findByLabelText('Global leaderboard');
    expect(mockedFetchLeaderboard).toHaveBeenCalledWith({ among: 'global' });

    fireEvent.press(await findByLabelText('Global leaderboard'));
    expect(mockedFetchLeaderboard).toHaveBeenCalledTimes(1);

    fireEvent.press(await findByLabelText('Friends leaderboard'));
    expect(mockedFetchLeaderboard).toHaveBeenCalledWith({ among: 'friends' });
  });

  it('shows scope-specific empty-state copy', async () => {
    mockedFetchLeaderboard.mockResolvedValue([]);
    const { findByText, findByLabelText } = renderScreen();

    expect(await findByText('Nobody on the board yet')).toBeTruthy();

    fireEvent.press(await findByLabelText('Friends leaderboard'));
    expect(await findByText('No friends ranked yet')).toBeTruthy();
  });

  it('shows a sign-in prompt on the Friends tab when signed out, instead of a false "no friends ranked" empty state', async () => {
    // Confirmed release defect (docs/SCREEN_UX_FINDINGS_TRIAGE.md): the
    // friends query is disabled entirely while signed out, so it fell
    // through to the generic empty-board copy -- misrepresenting "you're
    // not signed in" as "the board is genuinely empty."
    setAuth(null);
    mockedFetchLeaderboard.mockResolvedValue([]);
    const { findByText, findByLabelText, queryByText } = renderScreen();

    await findByText('Nobody on the board yet');
    fireEvent.press(await findByLabelText('Friends leaderboard'));

    expect(await findByText('Sign in to see your friends board')).toBeTruthy();
    expect(queryByText('No friends ranked yet')).toBeNull();
    expect(mockedFetchLeaderboard).not.toHaveBeenCalledWith({ among: 'friends' });

    fireEvent.press(await findByLabelText('Sign in'));
    expect(await findByText('auth')).toBeTruthy();
  });

  it('shows an error state with retry when the fetch fails, not the empty state', async () => {
    mockedFetchLeaderboard.mockRejectedValue(new Error('network'));
    const { findByText, queryByText } = renderScreen();
    expect(await findByText("Couldn't load the leaderboard")).toBeTruthy();
    expect(queryByText('Nobody on the board yet')).toBeNull();

    mockedFetchLeaderboard.mockResolvedValue([]);
    fireEvent.press(await findByText('Try again'));
    expect(await findByText('Nobody on the board yet')).toBeTruthy();
  });

  it('shows a medal for the top 3 ranks and a plain number otherwise', async () => {
    mockedFetchLeaderboard.mockResolvedValue([
      makeRow({ user_id: 'u1', rank: 1, display_name: 'First' }),
      makeRow({ user_id: 'u2', rank: 2, display_name: 'Second' }),
      makeRow({ user_id: 'u3', rank: 3, display_name: 'Third' }),
      makeRow({ user_id: 'u4', rank: 4, display_name: 'Fourth' }),
    ]);
    const { findByText } = renderScreen();

    expect(await findByText('🥇')).toBeTruthy();
    expect(await findByText('🥈')).toBeTruthy();
    expect(await findByText('🥉')).toBeTruthy();
    expect(await findByText('4')).toBeTruthy();
  });

  it('shows a separate handle line only when both display_name and username are present', async () => {
    mockedFetchLeaderboard.mockResolvedValue([
      // Both fields -- the name renders as "Both Fields" and a distinct
      // "@bothhandle" handle line appears underneath it.
      makeRow({ user_id: 'u1', display_name: 'Both Fields', username: 'bothhandle' }),
      // No display_name -- the label itself falls back to "@handleonly",
      // so the separate handle line's own condition (username AND
      // display_name) must not also render it a second time.
      makeRow({ user_id: 'u2', display_name: null, username: 'handleonly' }),
    ]);
    const { findByText, findAllByText } = renderScreen();

    expect(await findByText('Both Fields')).toBeTruthy();
    expect(await findByText('@bothhandle')).toBeTruthy();
    expect((await findAllByText('@handleonly')).length).toBe(1);
  });

  it('marks the signed-in user\'s own row as non-navigable and labeled "you"', async () => {
    mockedFetchLeaderboard.mockResolvedValue([makeRow({ user_id: 'me', display_name: 'Me Myself' })]);
    const { findByLabelText } = renderScreen();

    const row = await findByLabelText(/^Me Myself, rank 4/);
    fireEvent.press(row);
    expect(mockPush).not.toHaveBeenCalled();
  });

  it('navigates to another user\'s profile on tap', async () => {
    mockedFetchLeaderboard.mockResolvedValue([makeRow({ user_id: 'other-user', display_name: 'Other Person' })]);
    const { findByLabelText } = renderScreen();

    fireEvent.press(await findByLabelText(/^Other Person, rank 4/));
    expect(mockPush).toHaveBeenCalledWith('/user/other-user');
  });

  it('falls back to @username, then "Someone", when display_name is missing', async () => {
    mockedFetchLeaderboard.mockResolvedValue([
      makeRow({ user_id: 'u1', display_name: null, username: 'justahandle' }),
      makeRow({ user_id: 'u2', display_name: null, username: null }),
    ]);
    const { findByLabelText } = renderScreen();

    expect(await findByLabelText(/^@justahandle, rank 4/)).toBeTruthy();
    expect(await findByLabelText(/^Someone, rank 4/)).toBeTruthy();
  });
});
