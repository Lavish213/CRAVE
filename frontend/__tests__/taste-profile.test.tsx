// taste-profile/[userId].tsx — first dedicated coverage. Locks in: the
// not-found/blocked/no-data-yet state machine, the percentile ->
// "Top X%" framing (floored at 1), match_score's self-vs-other gating,
// the tier breakdown, the conditional favorite-cuisine/top-city cards,
// and the loadGenerationRef stale-response guard for a userId change.
import React from 'react';
import { act, fireEvent, render } from '@testing-library/react-native';
import TasteProfileScreen from '../app/taste-profile/[userId]';
import { useAuthStore } from '../src/stores/authStore';
import {
  Profile, TasteProfile, fetchBlockStatus, fetchProfile, fetchTasteProfile,
} from '../src/api/social';

let mockUserId = 'other-user';
jest.mock('expo-router', () => ({
  useLocalSearchParams: () => ({ userId: mockUserId }),
  useFocusEffect: (cb: () => void) => require('react').useEffect(cb, [cb]),
}));
jest.mock('../src/stores/authStore', () => ({
  useAuthStore: jest.fn(),
}));
jest.mock('../src/api/social', () => ({
  fetchProfile: jest.fn(),
  fetchBlockStatus: jest.fn(),
  fetchTasteProfile: jest.fn(),
}));

const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;
const mockedFetchProfile = fetchProfile as jest.MockedFunction<typeof fetchProfile>;
const mockedFetchBlockStatus = fetchBlockStatus as jest.MockedFunction<typeof fetchBlockStatus>;
const mockedFetchTasteProfile = fetchTasteProfile as jest.MockedFunction<typeof fetchTasteProfile>;

function setMe(id: string | null) {
  mockedUseAuthStore.mockImplementation((selector: (s: unknown) => unknown) =>
    selector({ user: id ? { id } : null }),
  );
}

function makeProfile(overrides: Partial<Profile> = {}): Profile {
  return { id: 'other-user', username: 'alice', display_name: 'Alice', avatar_url: null, bio: null, is_public: true, ...overrides };
}
function makeTaste(overrides: Partial<TasteProfile> = {}): TasteProfile {
  return {
    total_ranked: 12,
    tier_counts: { liked: 7, fine: 3, disliked: 2 },
    favorite_cuisine: null,
    top_city: null,
    percentile: null,
    match_score: null,
    ...overrides,
  };
}

describe('TasteProfileScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUserId = 'other-user';
    setMe('me');
    mockedFetchBlockStatus.mockResolvedValue({ blocked: false });
  });

  it('shows "Profile not found" on a 404', async () => {
    mockedFetchProfile.mockRejectedValue({ response: { status: 404 } });
    const { findByText } = render(<TasteProfileScreen />);
    expect(await findByText('Profile not found')).toBeTruthy();
  });

  it('shows a blocked message without ever fetching the taste profile', async () => {
    mockedFetchProfile.mockResolvedValue(makeProfile({ username: 'blockedguy' }));
    mockedFetchBlockStatus.mockResolvedValue({ blocked: true });

    const { findByText } = render(<TasteProfileScreen />);
    expect(await findByText("You've blocked @blockedguy.")).toBeTruthy();
    expect(mockedFetchTasteProfile).not.toHaveBeenCalled();
  });

  it('does not assume access when the block-status check fails', async () => {
    mockedFetchProfile.mockResolvedValue(makeProfile());
    mockedFetchBlockStatus.mockRejectedValue(new Error('network'));

    const { findByText } = render(<TasteProfileScreen />);

    expect(await findByText("Couldn't verify profile access")).toBeTruthy();
    expect(mockedFetchTasteProfile).not.toHaveBeenCalled();
  });

  it('shows a self-specific no-data message when viewing your own empty taste profile', async () => {
    mockUserId = 'me';
    setMe('me');
    mockedFetchProfile.mockResolvedValue(makeProfile({ id: 'me' }));
    mockedFetchTasteProfile.mockResolvedValue(makeTaste({ total_ranked: 0 }));

    const { findByText } = render(<TasteProfileScreen />);
    expect(await findByText("Rank a few places you've eaten and your taste profile will build up here.")).toBeTruthy();
    // Self view never checks block status against yourself.
    expect(mockedFetchBlockStatus).not.toHaveBeenCalled();
  });

  it('shows an other-specific no-data message when someone else has nothing ranked', async () => {
    mockedFetchProfile.mockResolvedValue(makeProfile({ username: 'newbie' }));
    mockedFetchTasteProfile.mockResolvedValue(makeTaste({ total_ranked: 0 }));

    const { findByText } = render(<TasteProfileScreen />);
    expect(await findByText("@newbie hasn't ranked anything yet.")).toBeTruthy();
  });

  it('renders the full profile: title, percentile framing, tier breakdown, and both cards', async () => {
    mockedFetchProfile.mockResolvedValue(makeProfile());
    mockedFetchTasteProfile.mockResolvedValue(makeTaste({
      percentile: 92, favorite_cuisine: 'Thai', top_city: { id: 'city-sf', name: 'San Francisco', count: 8 },
    }));

    const { findByText } = render(<TasteProfileScreen />);
    expect(await findByText("Alice's Taste Profile")).toBeTruthy();
    expect(await findByText('12')).toBeTruthy();
    // percentile=92 -> "top X%" is 100-92=8.
    expect(await findByText('Top 8%')).toBeTruthy();
    expect(await findByText('7')).toBeTruthy();
    expect(await findByText('3')).toBeTruthy();
    expect(await findByText('2')).toBeTruthy();
    expect(await findByText('Thai')).toBeTruthy();
    expect(await findByText('San Francisco · 8 ranked')).toBeTruthy();
  });

  it('floors the "top X%" framing at 1 for a top performer', async () => {
    mockedFetchProfile.mockResolvedValue(makeProfile());
    mockedFetchTasteProfile.mockResolvedValue(makeTaste({ percentile: 100 }));

    const { findByText, queryByText } = render(<TasteProfileScreen />);
    expect(await findByText('Top 1%')).toBeTruthy();
    expect(queryByText('Top 0%')).toBeNull();
  });

  it('shows "Your Taste Profile" and never a match score when viewing your own', async () => {
    mockUserId = 'me';
    setMe('me');
    mockedFetchProfile.mockResolvedValue(makeProfile({ id: 'me' }));
    mockedFetchTasteProfile.mockResolvedValue(makeTaste({ match_score: 88 }));

    const { findByText, queryByText } = render(<TasteProfileScreen />);
    expect(await findByText('Your Taste Profile')).toBeTruthy();
    expect(queryByText('88%')).toBeNull();
  });

  it('shows the match score only when viewing someone else and it is present', async () => {
    mockedFetchProfile.mockResolvedValue(makeProfile());
    mockedFetchTasteProfile.mockResolvedValue(makeTaste({ match_score: 61 }));

    const { findByText } = render(<TasteProfileScreen />);
    expect(await findByText('61%')).toBeTruthy();
  });

  it('does not render a previous profile\'s stale taste data under a new profile whose own taste fetch fails', async () => {
    // The confirmed Phase 3 bug: A's taste profile loads and renders in
    // full. Navigating to B succeeds on the *profile* fetch (so the
    // header correctly updates to B) but B's own taste fetch then fails
    // (network error, 5xx) -- the catch block only ever handles a 404, so
    // `taste` was previously left holding A's stale data untouched, which
    // then rendered in full under B's now-correct header.
    mockedFetchProfile.mockResolvedValue(makeProfile({ username: 'alice', display_name: 'Alice' }));
    mockedFetchTasteProfile.mockResolvedValue(makeTaste({ total_ranked: 12 }));

    const { rerender, findByText, queryByText } = render(<TasteProfileScreen />);
    expect(await findByText("Alice's Taste Profile")).toBeTruthy();
    expect(await findByText('12')).toBeTruthy();

    mockUserId = 'yet-another-user';
    mockedFetchProfile.mockResolvedValue(makeProfile({ id: 'yet-another-user', username: 'bob', display_name: 'Bob' }));
    mockedFetchTasteProfile.mockRejectedValue(new Error('network'));
    rerender(<TasteProfileScreen />);

    // Alice's stale total_ranked=12 must not still be showing once bob's
    // profile has loaded -- taste gets reset, not left holding alice's
    // data, so this correctly falls through to the same "nothing to show
    // yet" state a real empty taste profile would (a real fetch failure
    // here is a smaller, separate gap from the one this test covers:
    // stale cross-identity data must never render, whatever the resulting
    // empty/error copy).
    expect(await findByText("@bob hasn't ranked anything yet.")).toBeTruthy();
    expect(queryByText('12')).toBeNull();
    expect(queryByText("Alice's Taste Profile")).toBeNull();
  });

  it('reloads when the viewer switches accounts even though the profile being viewed stays the same', async () => {
    // isSelf (userId === me.id) is unchanged across this switch -- both
    // viewer-A and viewer-C are "not self" relative to the same target
    // profile -- so load()'s dependency array must include me.id itself,
    // not just isSelf, or this would never refetch and could go on
    // showing viewer A's block/taste view under viewer C's session.
    mockedFetchProfile.mockResolvedValue(makeProfile({ username: 'alice' }));
    mockedFetchBlockStatus.mockResolvedValue({ blocked: false });
    mockedFetchTasteProfile.mockResolvedValue(makeTaste({ total_ranked: 12 }));

    const { rerender, findByText, queryByText } = render(<TasteProfileScreen />);
    expect(await findByText('12')).toBeTruthy();

    setMe('viewer-c');
    mockedFetchBlockStatus.mockResolvedValue({ blocked: true });
    rerender(<TasteProfileScreen />);

    expect(await findByText("You've blocked @alice.")).toBeTruthy();
    expect(queryByText('12')).toBeNull();
  });

  it('does not let a stale response from a previous userId render under the new route', async () => {
    let resolveOld: (p: Profile) => void;
    mockedFetchProfile.mockImplementationOnce(
      () => new Promise((resolve) => { resolveOld = resolve; }),
    );
    mockedFetchTasteProfile.mockResolvedValue(makeTaste());

    const { rerender, findByText, queryByText } = render(<TasteProfileScreen />);
    // other-user's fetch is in flight, unresolved.

    mockUserId = 'yet-another-user';
    mockedFetchProfile.mockResolvedValue(makeProfile({ id: 'yet-another-user', display_name: 'New Person', username: 'newperson' }));
    rerender(<TasteProfileScreen />);
    await findByText("New Person's Taste Profile");

    await act(async () => {
      resolveOld!(makeProfile({ id: 'other-user', display_name: 'Stale Person' }));
    });
    expect(queryByText("Stale Person's Taste Profile")).toBeNull();
    expect(await findByText("New Person's Taste Profile")).toBeTruthy();
  });
});
