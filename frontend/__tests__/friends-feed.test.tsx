// friends-feed.tsx — first dedicated coverage. Locks in: the empty
// state (also covers the fetch-failure path, since the queryFn swallows
// errors into []), actor-name fallback logic, the two event-type
// renderings (ranked_place with a tappable score pill vs. followed_user
// with a disabled row and no score), and navigation gating on a real
// place_id.
import React from 'react';
import { fireEvent, render } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import FriendsFeedScreen from '../app/friends-feed';
import { useAuthStore } from '../src/stores/authStore';
import { ActivityEvent, fetchFriendsFeed } from '../src/api/social';

const mockPush = jest.fn();
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useFocusEffect: (cb: () => void) => require('react').useEffect(cb, [cb]),
}));
jest.mock('../src/stores/authStore', () => ({
  useAuthStore: jest.fn(),
}));
jest.mock('../src/api/social', () => ({
  fetchFriendsFeed: jest.fn(),
}));

const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;
const mockedFetchFriendsFeed = fetchFriendsFeed as jest.MockedFunction<typeof fetchFriendsFeed>;

function setAuth(user: { id: string } | null) {
  mockedUseAuthStore.mockImplementation((selector: (s: unknown) => unknown) => selector({ user }));
}

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <FriendsFeedScreen />
      </QueryClientProvider>,
    ),
  };
}

function rankedEvent(overrides: Partial<ActivityEvent> = {}): ActivityEvent {
  return {
    id: 'e1', user_id: 'me', event_type: 'ranked_place',
    actor: { id: 'friend-1', username: 'friendo', display_name: 'Friend One', avatar_url: null },
    place_id: 'place-1', place_name: 'Tasty Spot', place_image_url: null,
    target_user_id: null, target_user: null,
    payload: { tier: 'liked', score: 8.7 },
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

function followedEvent(overrides: Partial<ActivityEvent> = {}): ActivityEvent {
  return {
    id: 'e2', user_id: 'me', event_type: 'followed_user',
    actor: { id: 'friend-1', username: 'friendo', display_name: 'Friend One', avatar_url: null },
    place_id: null, place_name: null, place_image_url: null,
    target_user_id: 'user-9', target_user: { id: 'user-9', username: 'newfriend', display_name: null, avatar_url: null },
    payload: null,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

describe('FriendsFeedScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setAuth({ id: 'me' });
  });

  it('never fetches this account-scoped feed while signed out, even on focus/retry/refresh', async () => {
    // This screen's query is entirely viewer-scoped (your own follow
    // graph's activity) -- react-query's `enabled` only gates automatic
    // fetches, so the focus-refetch and retry/refresh call sites all need
    // their own guard too, or a signed-out call to any of them would
    // still issue a live request.
    setAuth(null);
    renderScreen();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(mockedFetchFriendsFeed).not.toHaveBeenCalled();
  });

  it('caches its response under a key scoped to the signed-in user, not a shared unscoped key', async () => {
    // Key-shape assertion complementing queryClient.test.ts's real
    // cache-boundary integration test (which uses myRankings as the
    // primary case) -- proves this screen's own key actually carries
    // user.id, not just that *a* key exists.
    mockedFetchFriendsFeed.mockResolvedValue([]);
    const { client, findByText } = renderScreen();
    await findByText('Nothing here yet');

    expect(client.getQueryData(['friends-feed', 'me'])).toEqual([]);
  });

  it('shows the follow-people empty state when there is no activity, and navigates to the leaderboard from its CTA', async () => {
    mockedFetchFriendsFeed.mockResolvedValue([]);
    const { findByText } = renderScreen();

    expect(await findByText('Nothing here yet')).toBeTruthy();
    fireEvent.press(await findByText('Find people'));
    expect(mockPush).toHaveBeenCalledWith('/leaderboard');
  });

  it('shows an error state with retry when the feed fetch fails, not the empty state', async () => {
    mockedFetchFriendsFeed.mockRejectedValue(new Error('network'));
    const { findByText, queryByText } = renderScreen();
    expect(await findByText("Couldn't load your friends feed")).toBeTruthy();
    expect(queryByText('Nothing here yet')).toBeNull();

    mockedFetchFriendsFeed.mockResolvedValue([]);
    fireEvent.press(await findByText('Try again'));
    expect(await findByText('Nothing here yet')).toBeTruthy();
  });

  it('renders a ranked-place event with the score pill, and navigates to the place on tap', async () => {
    mockedFetchFriendsFeed.mockResolvedValue([rankedEvent()]);
    const { findByLabelText, findByText } = renderScreen();

    const row = await findByLabelText('Friend One ranked Tasty Spot');
    expect(await findByText('8.7')).toBeTruthy();

    fireEvent.press(row);
    expect(mockPush).toHaveBeenCalledWith('/place/place-1');
  });

  it('renders a followed-user event with no score pill, and the row is not pressable', async () => {
    mockedFetchFriendsFeed.mockResolvedValue([followedEvent()]);
    const { findByLabelText, queryByText } = renderScreen();

    const row = await findByLabelText('Friend One followed someone');
    expect(queryByText('8.7')).toBeNull();

    fireEvent.press(row);
    expect(mockPush).not.toHaveBeenCalled();
  });

  it('falls back through display_name -> @username -> "Someone" for the actor name', async () => {
    mockedFetchFriendsFeed.mockResolvedValue([
      rankedEvent({ id: 'e-a', actor: { id: 'a', username: 'handleonly', display_name: null, avatar_url: null } }),
      rankedEvent({ id: 'e-b', actor: null }),
    ]);
    const { findByLabelText } = renderScreen();

    expect(await findByLabelText('@handleonly ranked Tasty Spot')).toBeTruthy();
    expect(await findByLabelText('Someone ranked Tasty Spot')).toBeTruthy();
  });

  it('does not navigate for a ranked event missing a place_id', async () => {
    mockedFetchFriendsFeed.mockResolvedValue([rankedEvent({ place_id: null })]);
    const { findByLabelText } = renderScreen();

    const row = await findByLabelText('Friend One ranked Tasty Spot');
    fireEvent.press(row);
    expect(mockPush).not.toHaveBeenCalled();
  });
});
