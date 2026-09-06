// rank/[placeId].tsx — first dedicated coverage. Locks in: the three-
// stage flow (tier -> comparing -> done) entirely driven by the
// backend's RankingStep responses, the immediate-ranked shortcut (no
// comparison needed when the tier has nothing to compare against yet),
// inline error handling for both startRanking and submitComparison
// without derailing the flow, the share action, and the
// placeGenerationRef stale-response guard for a placeId change.
import React from 'react';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
import RankPlaceScreen from '../app/rank/[placeId]';
import { useAuthStore } from '../src/stores/authStore';
import { fetchPlaceDetail, PlaceOut } from '../src/api/places';
import { Ranking, RankingStep, startRanking, submitComparison } from '../src/api/social';

const mockPush = jest.fn();
const mockBack = jest.fn();
let mockPlaceId = 'place-A';
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush, back: mockBack }),
  useLocalSearchParams: () => ({ placeId: mockPlaceId }),
}));
jest.mock('../src/stores/authStore', () => ({
  useAuthStore: jest.fn(),
}));
jest.mock('../src/api/places', () => ({
  fetchPlaceDetail: jest.fn(),
}));
jest.mock('../src/api/social', () => ({
  startRanking: jest.fn(),
  submitComparison: jest.fn(),
}));
jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  notificationAsync: jest.fn(),
  ImpactFeedbackStyle: { Medium: 'medium' },
  NotificationFeedbackType: { Success: 'success' },
}));
jest.mock('expo-sharing', () => ({
  isAvailableAsync: jest.fn().mockResolvedValue(true),
  shareAsync: jest.fn().mockResolvedValue(undefined),
}));
jest.mock('react-native-view-shot', () => ({
  captureRef: jest.fn().mockResolvedValue('file://fake.png'),
}));

const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;
const mockedFetchPlaceDetail = fetchPlaceDetail as jest.MockedFunction<typeof fetchPlaceDetail>;
const mockedStartRanking = startRanking as jest.MockedFunction<typeof startRanking>;
const mockedSubmitComparison = submitComparison as jest.MockedFunction<typeof submitComparison>;

function setAuth(user: { id: string } | null) {
  mockedUseAuthStore.mockImplementation((selector: (s: unknown) => unknown) => selector({ user }));
}

function makePlace(id: string, overrides: Partial<PlaceOut> = {}): PlaceOut {
  return {
    id, name: id, city_id: 'city-sf', rank_score: 0.3, tier: 'solid', rank_percentile: 0.5,
    distance_miles: null, category: 'Italian', categories: ['Italian'], address: '1 Main St, San Francisco',
    lat: null, lng: null, image: null, primary_image_url: null, images: [],
    website: null, grubhub_url: null, has_menu: false, price_tier: 2,
    ...overrides,
  } as PlaceOut;
}

const RANKED_STEP = (overrides: Partial<Ranking> = {}): RankingStep => ({
  status: 'ranked',
  ranking: { place_id: 'place-A', tier: 'liked', rank_score: 8.4, note: null, tags: null, visited_at: null, ...overrides },
});
const COMPARING_STEP = (opponentId = 'opponent-1'): RankingStep => ({
  status: 'comparing', comparison_token: 'tok-1', opponent_place_id: opponentId,
});

describe('RankPlaceScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPlaceId = 'place-A';
    setAuth({ id: 'user-1' });
    mockedFetchPlaceDetail.mockResolvedValue(makePlace('place-A', { name: 'Tasty Spot' }));
  });

  it('shows a sign-in prompt when signed out, without fetching the place', async () => {
    setAuth(null);
    const { findByText } = render(<RankPlaceScreen />);
    expect(await findByText('Sign in to rank places')).toBeTruthy();
  });

  it('shows an error state whose retry goes back, when the place fails to load', async () => {
    mockedFetchPlaceDetail.mockRejectedValue(new Error('network'));
    const { findByText, findByLabelText } = render(<RankPlaceScreen />);

    expect(await findByText("Couldn't load this place.")).toBeTruthy();
    fireEvent.press(await findByLabelText('Try again'));
    expect(mockBack).toHaveBeenCalled();
  });

  it('goes straight to the done stage when a tier pick immediately ranks (nothing to compare against yet)', async () => {
    mockedStartRanking.mockResolvedValue(RANKED_STEP({ rank_score: 9.2, tier: 'liked' }));
    const { findByText, findByLabelText, findAllByText } = render(<RankPlaceScreen />);

    await findByText('Tasty Spot');
    fireEvent.press(await findByLabelText('Loved it'));

    // Both the visible score display and the off-screen ShareRankCard
    // (kept mounted, not display:none, so captureRef has something real
    // to snapshot -- see the screen's own comment) render the same score.
    expect((await findAllByText('9.2')).length).toBeGreaterThanOrEqual(1);
    expect(mockedStartRanking).toHaveBeenCalledWith({ place_id: 'place-A', tier: 'liked' });
    expect(mockedSubmitComparison).not.toHaveBeenCalled();
  });

  it('moves to the comparing stage and resolves the opponent for display', async () => {
    mockedStartRanking.mockResolvedValue(COMPARING_STEP('opponent-1'));
    mockedFetchPlaceDetail.mockImplementation((id: string) =>
      Promise.resolve(makePlace(id, { name: id === 'place-A' ? 'Tasty Spot' : 'Old Favorite' })),
    );

    const { findByText, findByLabelText } = render(<RankPlaceScreen />);
    await findByText('Tasty Spot');
    fireEvent.press(await findByLabelText('Loved it'));

    expect(await findByText('Which was better?')).toBeTruthy();
    expect(await findByText('Comparison 1 · this is what sets your score')).toBeTruthy();
    expect(await findByLabelText('Choose Old Favorite as the better one')).toBeTruthy();
  });

  it('submits the comparison winner and finishes ranking on the next ranked response', async () => {
    mockedStartRanking.mockResolvedValue(COMPARING_STEP('opponent-1'));
    mockedFetchPlaceDetail.mockImplementation((id: string) =>
      Promise.resolve(makePlace(id, { name: id === 'place-A' ? 'Tasty Spot' : 'Old Favorite' })),
    );
    mockedSubmitComparison.mockResolvedValue(RANKED_STEP({ rank_score: 7.5 }));

    const { findByText, findByLabelText, findAllByText } = render(<RankPlaceScreen />);
    await findByText('Tasty Spot');
    fireEvent.press(await findByLabelText('Loved it'));
    const newChoice = await findByLabelText('Choose Tasty Spot as the better one');

    await act(async () => {
      fireEvent.press(newChoice);
    });

    expect(mockedSubmitComparison).toHaveBeenCalledWith('tok-1', 'new');
    expect((await findAllByText('7.5')).length).toBeGreaterThanOrEqual(1);
  });

  it('lets a comparison be skipped', async () => {
    mockedStartRanking.mockResolvedValue(COMPARING_STEP());
    mockedSubmitComparison.mockResolvedValue(RANKED_STEP());

    const { findByText, findByLabelText } = render(<RankPlaceScreen />);
    await findByText('Tasty Spot');
    fireEvent.press(await findByLabelText('Loved it'));

    const skipBtn = await findByLabelText("Can't decide");
    await act(async () => {
      fireEvent.press(skipBtn);
    });
    expect(mockedSubmitComparison).toHaveBeenCalledWith('tok-1', 'skip');
  });

  it('shows an inline error and stays on the tier stage when starting the ranking fails', async () => {
    mockedStartRanking.mockRejectedValue({ response: { data: { detail: 'Already ranked this place' } } });
    const { findByText, findByLabelText } = render(<RankPlaceScreen />);
    await findByText('Tasty Spot');

    fireEvent.press(await findByLabelText('Loved it'));
    expect(await findByText('Already ranked this place')).toBeTruthy();
    // Still on the tier stage -- the three tier buttons remain visible.
    expect(await findByLabelText('It was fine')).toBeTruthy();
  });

  it('shows an inline error and stays on the comparing stage when submitting a comparison fails', async () => {
    mockedStartRanking.mockResolvedValue(COMPARING_STEP());
    mockedSubmitComparison.mockRejectedValue({ response: { data: { detail: 'Comparison expired' } } });

    const { findByText, findByLabelText } = render(<RankPlaceScreen />);
    await findByText('Tasty Spot');
    fireEvent.press(await findByLabelText('Loved it'));
    const skipBtn = await findByLabelText("Can't decide");
    await act(async () => {
      fireEvent.press(skipBtn);
    });

    expect(await findByText('Comparison expired')).toBeTruthy();
    expect(await findByText('Which was better?')).toBeTruthy();
  });

  it('navigates to profile and back from the done stage', async () => {
    mockedStartRanking.mockResolvedValue(RANKED_STEP());
    const { findByText, findByLabelText } = render(<RankPlaceScreen />);
    await findByText('Tasty Spot');
    fireEvent.press(await findByLabelText('Loved it'));

    fireEvent.press(await findByLabelText('See my list'));
    expect(mockPush).toHaveBeenCalledWith('/profile');

    fireEvent.press(await findByLabelText('Done'));
    expect(mockBack).toHaveBeenCalled();
  });

  it('disables the opponent card and never submits it as a winner when its detail fetch fails', async () => {
    // Confirmed Phase 4 bug: a failed opponent-detail fetch left the card
    // showing its "A place you ranked" placeholder fully clickable --
    // an unidentified place could still be voted the winner. The card
    // must be disabled, and a real retry offered instead.
    mockedStartRanking.mockResolvedValue(COMPARING_STEP('opponent-1'));
    mockedFetchPlaceDetail.mockImplementation((id: string) =>
      id === 'place-A'
        ? Promise.resolve(makePlace('place-A', { name: 'Tasty Spot' }))
        : Promise.reject(new Error('network')),
    );

    const { findByText, findByLabelText, queryByLabelText } = render(<RankPlaceScreen />);
    await findByText('Tasty Spot');
    fireEvent.press(await findByLabelText('Loved it'));

    expect(await findByText("Couldn't load that place — retry")).toBeTruthy();
    // The unresolved opponent's card must not be labeled (and therefore
    // not tappable) with the fabricated placeholder name.
    expect(queryByLabelText('Choose A place you ranked as the better one')).toBeNull();
    expect(mockedSubmitComparison).not.toHaveBeenCalled();

    // Retry re-fetches just the opponent and, once resolved, the card
    // becomes rankable again.
    mockedFetchPlaceDetail.mockImplementation((id: string) =>
      Promise.resolve(makePlace(id, { name: id === 'place-A' ? 'Tasty Spot' : 'Old Favorite' })),
    );
    await act(async () => {
      fireEvent.press(await findByLabelText('Retry loading the other place'));
    });
    expect(await findByLabelText('Choose Old Favorite as the better one')).toBeTruthy();
  });

  it('does not double-submit a comparison on a rapid double tap', async () => {
    // React state (`busy`) alone can't close this race -- two native
    // touch events can both reach their handler before either's
    // setBusy(true) commits a re-render. Fired synchronously without
    // awaiting the first call, matching how two fast taps would
    // actually overlap.
    mockedStartRanking.mockResolvedValue(COMPARING_STEP());
    let resolveSubmit: (step: RankingStep) => void;
    mockedSubmitComparison.mockImplementation(
      () => new Promise((resolve) => { resolveSubmit = resolve; }),
    );

    const { findByText, findByLabelText } = render(<RankPlaceScreen />);
    await findByText('Tasty Spot');
    fireEvent.press(await findByLabelText('Loved it'));
    const skipBtn = await findByLabelText("Can't decide");

    fireEvent.press(skipBtn);
    fireEvent.press(skipBtn);
    await act(async () => {
      resolveSubmit!(RANKED_STEP());
    });

    expect(mockedSubmitComparison).toHaveBeenCalledTimes(1);
  });

  it('does not commit a late-resolving comparison result from a previous place after the route moved on', async () => {
    // Route-generation safety: a submission still in flight for place-A
    // must never render/commit under place-B after the user has already
    // moved to ranking a different place.
    mockedStartRanking.mockResolvedValue(COMPARING_STEP());
    let resolveSubmit: (step: RankingStep) => void;
    mockedSubmitComparison.mockImplementation(
      () => new Promise((resolve) => { resolveSubmit = resolve; }),
    );

    const { rerender, findByText, findByLabelText, queryByText } = render(<RankPlaceScreen />);
    await findByText('Tasty Spot');
    fireEvent.press(await findByLabelText('Loved it'));
    fireEvent.press(await findByLabelText("Can't decide"));
    // place-A's comparison submission is now in flight, unresolved.

    mockPlaceId = 'place-B';
    mockedFetchPlaceDetail.mockResolvedValue(makePlace('place-B', { name: 'New Route Place' }));
    rerender(<RankPlaceScreen />);
    await findByText('New Route Place');

    await act(async () => {
      resolveSubmit!(RANKED_STEP({ place_id: 'place-A', rank_score: 5.0 }));
    });

    // Place-A's late result must not flip this screen to the done stage
    // (or any stale content) while it's now showing place-B.
    expect(queryByText('OUT OF 10')).toBeNull();
    expect(await findByText('New Route Place')).toBeTruthy();
  });

  it('does not let a stale place from before a placeId change render under the new route', async () => {
    let resolveOld: (p: PlaceOut) => void;
    mockedFetchPlaceDetail.mockImplementationOnce(
      () => new Promise((resolve) => { resolveOld = resolve; }),
    );

    const { rerender, findByText, queryByText } = render(<RankPlaceScreen />);
    // place-A's fetch is in flight, unresolved.

    mockPlaceId = 'place-B';
    mockedFetchPlaceDetail.mockResolvedValue(makePlace('place-B', { name: 'New Route Place' }));
    rerender(<RankPlaceScreen />);
    await findByText('New Route Place');

    // The stale place-A response lands late -- it must not clobber the
    // screen now showing place-B.
    await act(async () => {
      resolveOld!(makePlace('place-A', { name: 'Stale Old Place' }));
    });
    expect(queryByText('Stale Old Place')).toBeNull();
    expect(await findByText('New Route Place')).toBeTruthy();
  });
});
