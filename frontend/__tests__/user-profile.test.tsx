// user/[id].tsx — first dedicated coverage. Locks in: the not-found
// state, self-vs-other view differences (no follow button/options menu
// on your own profile), the "Follows you" badge, optimistic follow/
// unfollow with revert-on-failure, the two-step block confirm flow
// (which also immediately clears following/followsMe client-side,
// matching the server's own follow-severing behavior), the inline
// unblock link, the ranked-list rendering plus its Taste Profile link
// gating, and a loadGenerationRef stale-response test for an id change.
import React from 'react';
import { Alert } from 'react-native';
import { act, fireEvent, render } from '@testing-library/react-native';
import UserProfileScreen from '../app/user/[id]';
import { useAuthStore } from '../src/stores/authStore';
import {
  Profile, RankedPlace,
  blockUser, fetchBlockStatus, fetchFollowStatus, fetchProfile, fetchUserRankings,
  followUser, unblockUser, unfollowUser,
} from '../src/api/social';

const mockPush = jest.fn();
let mockId = 'other-user';
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useLocalSearchParams: () => ({ id: mockId }),
  useFocusEffect: (cb: () => void) => require('react').useEffect(cb, [cb]),
}));
jest.mock('../src/stores/authStore', () => ({
  useAuthStore: jest.fn(),
}));
jest.mock('../src/api/social', () => ({
  fetchProfile: jest.fn(),
  fetchUserRankings: jest.fn(),
  fetchFollowStatus: jest.fn(),
  fetchBlockStatus: jest.fn(),
  followUser: jest.fn(),
  unfollowUser: jest.fn(),
  blockUser: jest.fn(),
  unblockUser: jest.fn(),
}));
jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'light', Medium: 'medium' },
}));

const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;
const mockedFetchProfile = fetchProfile as jest.MockedFunction<typeof fetchProfile>;
const mockedFetchUserRankings = fetchUserRankings as jest.MockedFunction<typeof fetchUserRankings>;
const mockedFetchFollowStatus = fetchFollowStatus as jest.MockedFunction<typeof fetchFollowStatus>;
const mockedFetchBlockStatus = fetchBlockStatus as jest.MockedFunction<typeof fetchBlockStatus>;
const mockedFollowUser = followUser as jest.MockedFunction<typeof followUser>;
const mockedUnfollowUser = unfollowUser as jest.MockedFunction<typeof unfollowUser>;
const mockedBlockUser = blockUser as jest.MockedFunction<typeof blockUser>;
const mockedUnblockUser = unblockUser as jest.MockedFunction<typeof unblockUser>;

function setMe(id: string | null) {
  mockedUseAuthStore.mockImplementation((selector: (s: unknown) => unknown) =>
    selector({ user: id ? { id } : null }),
  );
}
function makeProfile(overrides: Partial<Profile> = {}): Profile {
  return { id: 'other-user', username: 'alice', display_name: 'Alice', avatar_url: null, bio: null, is_public: true, ...overrides };
}
function makeRanking(place_id: string, overrides: Partial<RankedPlace> = {}): RankedPlace {
  return { place_id, tier: 'liked', rank_score: 8.0, note: null, tags: null, visited_at: null, name: place_id, primary_image_url: null, city_id: null, ...overrides } as RankedPlace;
}

function pressAlertButton(buttonText: string) {
  const calls = (Alert.alert as jest.Mock).mock.calls;
  const call = calls[calls.length - 1];
  const buttons = call[2] as { text: string; onPress?: () => void }[];
  buttons.find((b) => b.text === buttonText)?.onPress?.();
}

describe('UserProfileScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(Alert, 'alert').mockImplementation(() => {});
    mockId = 'other-user';
    setMe('me');
    mockedFetchUserRankings.mockResolvedValue([]);
    mockedFetchFollowStatus.mockResolvedValue({ following: false, followed_by: false });
    mockedFetchBlockStatus.mockResolvedValue({ blocked: false });
  });

  it('shows "Profile not found" on a 404', async () => {
    mockedFetchProfile.mockRejectedValue({ response: { status: 404 } });
    const { findByText } = render(<UserProfileScreen />);
    expect(await findByText('Profile not found')).toBeTruthy();
  });

  it('does not describe a network/5xx failure on the profile fetch as a nonexistent account', async () => {
    // Previously any non-404 error on fetchProfile (network failure,
    // timeout, 500) collapsed into the exact same "Profile not found"
    // EmptyState as a genuine 404, with no retry -- a transient
    // infrastructure failure is not the same product truth, and unlike
    // a real 404, it's retryable.
    mockedFetchProfile.mockRejectedValue(new Error('network'));
    const { findByText, queryByText } = render(<UserProfileScreen />);
    expect(await findByText("Couldn't load this profile")).toBeTruthy();
    expect(queryByText('Profile not found')).toBeNull();
  });

  it('routes a 401 from the route-level API-key gate (require_api_key) through the same retryable error, not a distinct auth state', async () => {
    // require_api_key (a route dependency, separate from the optional
    // viewer-identity dependency this route also takes) 401s with
    // "Invalid API key" when API_KEY is configured and x-api-key is
    // missing/wrong -- a real, reachable 401, just not through the
    // viewer-auth path. No new state needed: it already falls into the
    // same non-404 bucket as any other profile-fetch failure.
    mockedFetchProfile.mockRejectedValue({ response: { status: 401, data: { detail: 'Invalid API key' } } });
    const { findByText, queryByText } = render(<UserProfileScreen />);
    expect(await findByText("Couldn't load this profile")).toBeTruthy();
    expect(queryByText('Profile not found')).toBeNull();
  });

  it('recovers on retry after a transient profile-fetch failure, instead of staying stuck on the error', async () => {
    // Confirmed by CodeRabbit: profileError was only ever cleared inside
    // the identity-change reset block, so a same-identity retry (this
    // screen's own onRetry={load}) that actually succeeded still
    // rendered the stale ErrorState over the freshly-loaded, perfectly
    // good data -- the flag never cleared for a same-identity attempt.
    mockedFetchProfile.mockRejectedValueOnce(new Error('network'));
    const { findByText, findByLabelText, queryByText } = render(<UserProfileScreen />);
    expect(await findByText("Couldn't load this profile")).toBeTruthy();

    mockedFetchProfile.mockResolvedValue(makeProfile());
    await act(async () => {
      fireEvent.press(await findByLabelText('Try again'));
    });

    expect(await findByText('Alice')).toBeTruthy();
    expect(queryByText("Couldn't load this profile")).toBeNull();
  });

  it('hides the follow button and options menu on your own profile', async () => {
    mockId = 'me';
    setMe('me');
    mockedFetchProfile.mockResolvedValue(makeProfile({ id: 'me' }));

    const { findByText, queryByLabelText } = render(<UserProfileScreen />);
    await findByText('Alice');
    expect(queryByLabelText('Follow alice')).toBeNull();
    expect(queryByLabelText('More options')).toBeNull();
    // Self view never checks follow/block status against yourself.
    expect(mockedFetchFollowStatus).not.toHaveBeenCalled();
    expect(mockedFetchBlockStatus).not.toHaveBeenCalled();
  });

  it('shows the "Follows you" badge when they follow you back', async () => {
    mockedFetchProfile.mockResolvedValue(makeProfile());
    mockedFetchFollowStatus.mockResolvedValue({ following: false, followed_by: true });

    const { findByText } = render(<UserProfileScreen />);
    expect(await findByText('Follows you')).toBeTruthy();
  });

  it('follows optimistically, and reverts if the request fails', async () => {
    mockedFetchProfile.mockResolvedValue(makeProfile());
    mockedFollowUser.mockRejectedValue(new Error('server error'));

    const { findByLabelText } = render(<UserProfileScreen />);
    const followBtn = await findByLabelText('Follow alice');

    await act(async () => {
      fireEvent.press(followBtn);
    });

    // Reverted back to "Follow" after the failed request.
    expect(await findByLabelText('Follow alice')).toBeTruthy();
  });

  it('unfollows on tapping an already-following button', async () => {
    mockedFetchProfile.mockResolvedValue(makeProfile());
    mockedFetchFollowStatus.mockResolvedValue({ following: true, followed_by: false });
    mockedUnfollowUser.mockResolvedValue(undefined as any);

    const { findByLabelText } = render(<UserProfileScreen />);
    const unfollowBtn = await findByLabelText('Unfollow alice');
    await act(async () => {
      fireEvent.press(unfollowBtn);
    });

    expect(mockedUnfollowUser).toHaveBeenCalledWith('other-user');
    expect(await findByLabelText('Follow alice')).toBeTruthy();
  });

  it('blocks through the two-step options-menu confirm, and immediately clears follow state both ways', async () => {
    mockedFetchProfile.mockResolvedValue(makeProfile());
    mockedFetchFollowStatus.mockResolvedValue({ following: true, followed_by: true });
    mockedBlockUser.mockResolvedValue(undefined as any);

    const { findByLabelText, findByText, queryByLabelText } = render(<UserProfileScreen />);
    await findByLabelText('Unfollow alice');

    fireEvent.press(await findByLabelText('More options'));
    pressAlertButton('Block user');
    expect(mockedBlockUser).not.toHaveBeenCalled();

    await act(async () => {
      pressAlertButton('Block');
    });

    expect(mockedBlockUser).toHaveBeenCalledWith('other-user');
    expect(await findByText("You've blocked @alice. Their activity is hidden from you.")).toBeTruthy();
    expect(queryByLabelText('Unfollow alice')).toBeNull();
    expect(queryByLabelText('Follows you')).toBeNull();
  });

  it('unblocks from the inline link on the blocked notice', async () => {
    mockedFetchProfile.mockResolvedValue(makeProfile());
    mockedFetchBlockStatus.mockResolvedValue({ blocked: true });
    mockedUnblockUser.mockResolvedValue(undefined as any);

    const { findByText, queryByText } = render(<UserProfileScreen />);
    const unblockLink = await findByText('Unblock');
    await act(async () => {
      fireEvent.press(unblockLink);
    });

    expect(mockedUnblockUser).toHaveBeenCalledWith('other-user');
    expect(queryByText("You've blocked @alice. Their activity is hidden from you.")).toBeNull();
  });

  it('shows an alert if blocking fails, without marking them blocked', async () => {
    mockedFetchProfile.mockResolvedValue(makeProfile());
    mockedBlockUser.mockRejectedValue(new Error('server error'));

    const { findByLabelText, queryByText } = render(<UserProfileScreen />);
    fireEvent.press(await findByLabelText('More options'));
    pressAlertButton('Block user');
    await act(async () => {
      pressAlertButton('Block');
    });

    expect(Alert.alert).toHaveBeenCalledWith("Couldn't block", 'Something went wrong. Try again.');
    expect(queryByText("You've blocked @alice. Their activity is hidden from you.")).toBeNull();
  });

  it('shows the empty-ranked-list text and hides the Taste Profile link when nothing is ranked', async () => {
    mockedFetchProfile.mockResolvedValue(makeProfile());
    const { findByText, queryByLabelText } = render(<UserProfileScreen />);

    expect(await findByText("@alice hasn't ranked anything yet.")).toBeTruthy();
    expect(queryByLabelText("View alice's Taste Profile")).toBeNull();
  });

  it('does not describe a failed rankings request as an empty ranked list', async () => {
    mockedFetchProfile.mockResolvedValue(makeProfile());
    mockedFetchUserRankings.mockRejectedValue(new Error('network'));

    const { findByText, queryByText } = render(<UserProfileScreen />);

    expect(await findByText("Couldn't load ranked places")).toBeTruthy();
    expect(queryByText("@alice hasn't ranked anything yet.")).toBeNull();
  });

  it('hides relationship actions when their status cannot be verified', async () => {
    mockedFetchProfile.mockResolvedValue(makeProfile());
    mockedFetchFollowStatus.mockRejectedValue(new Error('network'));

    const { findByText, queryByLabelText } = render(<UserProfileScreen />);

    expect(await findByText("Couldn't load relationship controls")).toBeTruthy();
    expect(queryByLabelText('Follow alice')).toBeNull();
    expect(queryByLabelText('More options')).toBeNull();
  });

  it('renders ranked rows, shows the Taste Profile link, and navigates on tap', async () => {
    mockedFetchProfile.mockResolvedValue(makeProfile());
    mockedFetchUserRankings.mockResolvedValue([makeRanking('p0', { name: 'Great Place', rank_score: 9.0 })]);

    const { findByLabelText } = render(<UserProfileScreen />);
    const tasteLink = await findByLabelText("View alice's Taste Profile");
    fireEvent.press(tasteLink);
    expect(mockPush).toHaveBeenCalledWith('/taste-profile/other-user');

    const row = await findByLabelText(/^Great Place, ranked number 1/);
    fireEvent.press(row);
    expect(mockPush).toHaveBeenCalledWith('/place/p0');
  });

  it('clears the previous person\'s data immediately on an id change, before the new person\'s fetch resolves', async () => {
    // Distinct from the stale-response test below: `loading` previously
    // only ever flipped back to false from the *first* load's own finally
    // block -- a second load() (a real id change while this screen
    // instance is reused, not a remount) never set it back to true, so
    // this screen fell through the `if (loading)` skeleton gate and kept
    // rendering the *previous* person's profile/rankings with no loading
    // indicator until the new person's fetch happened to resolve.
    mockedFetchProfile.mockResolvedValue(makeProfile({ display_name: 'Alice' }));
    mockedFetchUserRankings.mockResolvedValue([makeRanking('p0', { name: 'Old Person Place' })]);

    const { rerender, findByText, queryByText } = render(<UserProfileScreen />);
    expect(await findByText('Old Person Place')).toBeTruthy();

    mockId = 'yet-another-user';
    mockedFetchProfile.mockImplementationOnce(() => new Promise(() => {}));
    rerender(<UserProfileScreen />);

    expect(queryByText('Old Person Place')).toBeNull();
    expect(queryByText('Alice')).toBeNull();
  });

  it('does not let a stale response from a previous id render under the new route', async () => {
    let resolveOld: (p: Profile) => void;
    mockedFetchProfile.mockImplementationOnce(
      () => new Promise((resolve) => { resolveOld = resolve; }),
    );

    const { rerender, findByText, queryByText } = render(<UserProfileScreen />);

    mockId = 'yet-another-user';
    mockedFetchProfile.mockResolvedValue(makeProfile({ id: 'yet-another-user', display_name: 'New Person', username: 'newperson' }));
    rerender(<UserProfileScreen />);
    await findByText('New Person');

    await act(async () => {
      resolveOld!(makeProfile({ id: 'other-user', display_name: 'Stale Person' }));
    });
    expect(queryByText('Stale Person')).toBeNull();
    expect(await findByText('New Person')).toBeTruthy();
  });
});
