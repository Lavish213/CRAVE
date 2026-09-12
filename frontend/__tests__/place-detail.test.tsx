// Focused render coverage for the Place Detail visual-language pass
// (2026-08-26): confirms the redesign didn't change any real behavior --
// only asserts on things this pass touched (why-this-fits suppression,
// the no-photos accessible empty state, menu-item accessible grouping,
// save/unsave state) or things it promised not to touch (accessibility
// labels still present, section headers still marked as headers).
// Not a full regression suite for the stale-response guards or upload/
// moderation branching -- neither was touched by this pass, and both
// already have their own established behavior from prior sessions.
import React from 'react';
import { Share } from 'react-native';
import { render, waitFor, fireEvent } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import PlaceDetailScreen from '../app/place/[id]';
import { fetchPlaceDetail, fetchPlaceRelationship } from '../src/api/places';
import { getPlaceMenu } from '../src/api/menu';
import { getCravesForPlace } from '../src/api/crave';
import { fetchMyRankings, fetchFriendRankings } from '../src/api/social';

// This screen now settles strictly more async work per render than when
// this file's default 5000ms budget was set (Wave 7 added a third
// react-query -- GET /place/{id}/relationship -- on top of the existing
// place/myRankings queries and the menu/craves/friendRankings effects).
// Seen timing out under CI's shared runners, not locally; widened rather
// than guessed at, matching the same fix already applied to
// search.test.tsx's CI-only retry-timeout flake this session.
jest.setTimeout(15000);

const mockRouterPush = jest.fn();
const mockSetOptions = jest.fn();
jest.mock('expo-router', () => ({
  useLocalSearchParams: jest.fn(() => ({ id: 'place-1' })),
  useNavigation: () => ({ setOptions: mockSetOptions }),
  useRouter: () => ({ push: mockRouterPush }),
}));
jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  notificationAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'light', Medium: 'medium' },
  NotificationFeedbackType: { Success: 'success', Warning: 'warning', Error: 'error' },
}));
jest.mock('../src/api/places', () => ({
  fetchPlaceDetail: jest.fn(),
  fetchPlaceRelationship: jest.fn(),
}));
jest.mock('../src/api/menu', () => ({ getPlaceMenu: jest.fn() }));
jest.mock('../src/api/crave', () => ({ getCravesForPlace: jest.fn() }));
jest.mock('../src/api/social', () => ({
  fetchMyRankings: jest.fn().mockResolvedValue([]),
  fetchFriendRankings: jest.fn().mockResolvedValue([]),
}));
jest.mock('../src/api/cities', () => ({ fetchCities: jest.fn().mockResolvedValue([]) }));
jest.mock('../src/hooks/useLocation', () => ({ useLocation: () => null }));
// All three pull in api/upload.ts -> api/client.ts -> lib/supabase.ts,
// same poisonous import chain every other screen test mocks around.
// None of the tests below exercise the upload flow (untouched by this
// pass), so a no-op is all that's needed.
jest.mock('../src/hooks/useImagePicker', () => ({ useImagePicker: () => ({ pick: jest.fn() }) }));
jest.mock('../src/hooks/useUploadImage', () => ({ useUploadImage: () => ({ upload: jest.fn() }) }));
jest.mock('../src/hooks/useImageStatusPoll', () => ({
  useImageStatusPoll: () => ({ status: null, error: null, moderationStatus: null }),
}));
jest.mock('../src/stores/authStore', () => ({ useAuthStore: jest.fn() }));
const mockRequestAuthGate = jest.fn();
jest.mock('../src/stores/authGateStore', () => ({
  requestAuthGate: (...args: unknown[]) => mockRequestAuthGate(...args),
}));
jest.mock('../src/stores/cravesStore', () => {
  const state = {
    addSave: jest.fn(),
    removeSave: jest.fn(),
    isSaved: jest.fn(() => false),
    saves: [] as any[],
    setSaveMemory: jest.fn(),
  };
  const hook: any = () => state;
  hook.getState = () => state;
  return { useCravesStore: hook, __state: state };
});
jest.mock('../src/components/PlaceVideoGallery', () => ({ PlaceVideoGallery: () => null }));
jest.mock('../src/components/ReportPhotoSheet', () => ({ ReportPhotoSheet: () => null }));
jest.mock('../src/components/ReportPlaceSheet', () => ({ ReportPlaceSheet: () => null }));
jest.mock('../src/components/MenuSubmissionSheet', () => ({ MenuSubmissionSheet: () => null }));

import { useAuthStore } from '../src/stores/authStore';
import { useLocalSearchParams } from 'expo-router';
const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;
const mockedUseLocalSearchParams = useLocalSearchParams as jest.Mock;
const cravesStoreState = (jest.requireMock('../src/stores/cravesStore') as any).__state;

// Stable reference across renders -- a fresh object literal returned from
// useAuthStore's mock every call would retrigger the friendRankings
// effect (keyed on [id, user]) forever, since it'd look like a new user
// on every render.
const mockAuthUser = { id: 'user-1' };

const mockedFetchPlaceDetail = fetchPlaceDetail as jest.MockedFunction<typeof fetchPlaceDetail>;
const mockedFetchPlaceRelationship = fetchPlaceRelationship as jest.MockedFunction<typeof fetchPlaceRelationship>;
const mockedGetPlaceMenu = getPlaceMenu as jest.MockedFunction<typeof getPlaceMenu>;
const mockedGetCravesForPlace = getCravesForPlace as jest.MockedFunction<typeof getCravesForPlace>;

function baseRelationship(overrides: Partial<any> = {}) {
  return {
    saved: false,
    visited: false,
    visited_at: null,
    notes: null,
    reason_role: null,
    reason_source: null,
    visit_confirmation_count: 0,
    visit_evidence_tier: null,
    ...overrides,
  } as any;
}

function basePlace(overrides: Partial<any> = {}) {
  return {
    id: 'place-1',
    name: 'Nari',
    category: 'Thai',
    address: '123 Main St, San Francisco',
    price: '$$$',
    rank_percentile: 0.97,
    city_id: 'city-sf',
    images: ['https://example.com/a.jpg'],
    image: null,
    image_gps_verified: [false],
    image_ids: [],
    website: null,
    grubhub_url: null,
    lat: 37.79,
    lng: -122.4,
    has_menu: true,
    rank_score: 0.9,
    tier: 'crave_pick',
    distance_miles: null,
    categories: ['Thai'],
    price_tier: 3,
    ...overrides,
  } as any;
}

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <PlaceDetailScreen />
    </QueryClientProvider>,
  );
}

describe('PlaceDetailScreen — visual-pass regression coverage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    cravesStoreState.isSaved.mockReturnValue(false);
    cravesStoreState.saves = [];
    mockedUseAuthStore.mockImplementation((selector: (s: { user: unknown }) => unknown) =>
      selector({ user: mockAuthUser }),
    );
    mockedGetCravesForPlace.mockResolvedValue([]);
    mockedGetPlaceMenu.mockResolvedValue({ items: [], lastVerifiedAt: null } as any);
    mockedFetchPlaceRelationship.mockResolvedValue(baseRelationship());
    mockedUseLocalSearchParams.mockReturnValue({ id: 'place-1' });
  });

  it('renders identity as a header and "why this fits" with a real percentile', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    const { getAllByText, findAllByText, getByText } = renderScreen();

    await findAllByText('Nari');
    expect(getAllByText('Nari')[0].props.accessibilityRole).toBe('header');
    expect(getByText(/top 3% in San Francisco|CRAVE Pick/)).toBeTruthy();
  });

  it('suppresses "why this fits" entirely when there is no percentile and no friend signal', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace({ rank_percentile: null }));
    const { findByText, queryByText } = renderScreen();

    await findByText('Nari');
    expect(queryByText(/top \d+%/)).toBeNull();
  });

  it('shows the accessible no-photos state instead of a stretched fallback image', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace({ images: [], image: null }));
    const { findByText, getByLabelText } = renderScreen();

    await findByText('Nari');
    expect(getByLabelText('No photos yet for Nari')).toBeTruthy();
  });

  it('groups a menu item into one accessible element (name, description, price)', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    mockedGetPlaceMenu.mockResolvedValue({
      items: [{ id: 'm1', name: 'Pad Thai', description: 'Rice noodles', price: 16, category: null }],
      lastVerifiedAt: null,
    } as any);
    const { findByLabelText } = renderScreen();

    expect(await findByLabelText('Pad Thai, Rice noodles, $16.00')).toBeTruthy();
  });

  it('reflects saved state in the Save button label', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    cravesStoreState.isSaved.mockReturnValue(true);
    const { findByLabelText } = renderScreen();

    expect(await findByLabelText('Remove from Saves')).toBeTruthy();
  });

  it('shows an offline-specific message for a network-level failure, distinct from a real server error', async () => {
    mockedFetchPlaceDetail.mockRejectedValue(new Error('Network Error'));
    const { findByText } = renderScreen();

    expect(await findByText("Can't reach CRAVE — check your connection.")).toBeTruthy();
  });

  it('shows the generic message for a real server error (has a response)', async () => {
    const err: any = new Error('Server Error');
    err.response = { status: 500 };
    mockedFetchPlaceDetail.mockRejectedValue(err);
    const { findByText } = renderScreen();

    expect(await findByText("Couldn't load this place")).toBeTruthy();
  });

  it('does not describe a failed menu fetch as "no menu on file", and offers a retry', async () => {
    // Phase 3 confirmed bug: the menu fetch's .catch() reset menuItems to
    // [] with no distinguishing flag, so a network/5xx failure rendered
    // the exact same "Menu coming soon"/"No menu on file yet" copy a
    // genuinely empty (200, items: []) menu gets -- the place itself
    // (a separate resource) still loads fine and must stay usable.
    mockedFetchPlaceDetail.mockResolvedValue(basePlace({ has_menu: true }));
    mockedGetPlaceMenu.mockRejectedValue(new Error('network'));
    const { findByText, findByLabelText, queryByText } = renderScreen();

    await findByText('Nari');
    expect(await findByText("Couldn't load the menu")).toBeTruthy();
    expect(queryByText('Menu coming soon')).toBeNull();
    expect(queryByText('No menu on file yet')).toBeNull();

    mockedGetPlaceMenu.mockResolvedValue({
      items: [{ id: 'm1', name: 'Pad Thai', description: null, price: null, category: null }],
      lastVerifiedAt: null,
    } as any);
    const retryBtn = await findByLabelText('Retry loading the menu');
    fireEvent.press(retryBtn);

    expect(await findByText('Pad Thai')).toBeTruthy();
  });
});

describe('PlaceDetailScreen — visited/notes memory (E2)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    cravesStoreState.isSaved.mockReturnValue(false);
    cravesStoreState.saves = [];
    mockedUseAuthStore.mockImplementation((selector: (s: { user: unknown }) => unknown) =>
      selector({ user: mockAuthUser }),
    );
    mockedGetCravesForPlace.mockResolvedValue([]);
    mockedGetPlaceMenu.mockResolvedValue({ items: [], lastVerifiedAt: null } as any);
    mockedFetchPlaceRelationship.mockResolvedValue(baseRelationship());
    mockedUseLocalSearchParams.mockReturnValue({ id: 'place-1' });
  });

  it('does not render the visited/notes section for a place that is not saved', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    const { findByText, queryByLabelText } = renderScreen();

    await findByText('Nari');
    expect(queryByLabelText('Notes about this place')).toBeNull();
    expect(queryByLabelText(/I've been here|You've been here/)).toBeNull();
  });

  it('shows "I\'ve been here" for a saved, not-yet-visited place', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    cravesStoreState.saves = [{ ...basePlace(), visited: false, visited_at: null, notes: null }];
    const { findByLabelText } = renderScreen();

    expect(await findByLabelText('Mark as visited')).toBeTruthy();
  });

  it('shows "You\'ve been here" once visited, and toggling calls setSaveMemory with the flipped value', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    cravesStoreState.saves = [{ ...basePlace(), visited: true, visited_at: '2026-09-01T00:00:00Z', notes: null }];
    cravesStoreState.setSaveMemory.mockResolvedValue(null);
    const { findByLabelText } = renderScreen();

    const toggle = await findByLabelText('Mark as not visited');
    fireEvent.press(toggle);
    await waitFor(() =>
      expect(cravesStoreState.setSaveMemory).toHaveBeenCalledWith('place-1', { visited: false }),
    );
  });

  it('prefills the notes field from the saved entry and only shows Save note once the draft actually changes', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    cravesStoreState.saves = [{ ...basePlace(), visited: false, visited_at: null, notes: 'great patio' }];
    const { findByDisplayValue, queryByLabelText, getByLabelText } = renderScreen();

    const input = await findByDisplayValue('great patio');
    expect(queryByLabelText('Save note')).toBeNull();

    fireEvent.changeText(input, 'great patio, ask for the corner table');
    expect(getByLabelText('Save note')).toBeTruthy();
  });

  it('saves an edited note by calling setSaveMemory with the trimmed text', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    cravesStoreState.saves = [{ ...basePlace(), visited: false, visited_at: null, notes: '' }];
    cravesStoreState.setSaveMemory.mockResolvedValue(null);
    const { findByLabelText, getByLabelText } = renderScreen();

    const input = await findByLabelText('Notes about this place');
    fireEvent.changeText(input, '  ask for the corner table  ');
    fireEvent.press(getByLabelText('Save note'));
    await waitFor(() =>
      expect(cravesStoreState.setSaveMemory).toHaveBeenCalledWith('place-1', {
        notes: 'ask for the corner table',
      }),
    );
  });

  it('clears notes (sends null, not empty string) when the field is emptied', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    cravesStoreState.saves = [{ ...basePlace(), visited: false, visited_at: null, notes: 'old note' }];
    cravesStoreState.setSaveMemory.mockResolvedValue(null);
    const { findByDisplayValue, getByLabelText } = renderScreen();

    const input = await findByDisplayValue('old note');
    fireEvent.changeText(input, '');
    fireEvent.press(getByLabelText('Save note'));
    await waitFor(() =>
      expect(cravesStoreState.setSaveMemory).toHaveBeenCalledWith('place-1', { notes: null }),
    );
  });
});

describe('PlaceDetailScreen — Wave 7 relationship hierarchy', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    cravesStoreState.isSaved.mockReturnValue(false);
    cravesStoreState.saves = [];
    mockedUseAuthStore.mockImplementation((selector: (s: { user: unknown }) => unknown) =>
      selector({ user: mockAuthUser }),
    );
    mockedGetCravesForPlace.mockResolvedValue([]);
    mockedGetPlaceMenu.mockResolvedValue({ items: [], lastVerifiedAt: null } as any);
    mockedFetchPlaceRelationship.mockResolvedValue(baseRelationship());
    mockedUseLocalSearchParams.mockReturnValue({ id: 'place-1' });
  });

  it('shows Directions as the primary CTA for an unvisited place with coordinates', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    const { findByLabelText, queryByLabelText } = renderScreen();

    expect(await findByLabelText('Get directions')).toBeTruthy();
    // Not duplicated in the decision-strip facts row once promoted to primary.
    expect(queryByLabelText('Rank this place')).toBeNull();
  });

  it('falls back to a Save primary CTA for an unvisited place with no coordinates', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace({ lat: null, lng: null }));
    const { findByLabelText, queryByLabelText } = renderScreen();

    expect(await findByLabelText('Save for tonight')).toBeTruthy();
    expect(queryByLabelText('Get directions')).toBeNull();
  });

  it('shows a relationship-status block and "Rank it" once visited, stopping the persuasive "why this fits"', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    cravesStoreState.saves = [{ ...basePlace(), visited: true, visited_at: '2026-09-01T00:00:00Z', notes: null, visit_confirmation_count: 1 }];
    const { findByText, findByLabelText, queryByText } = renderScreen();

    expect(await findByText('Already on your list of visits')).toBeTruthy();
    expect(await findByLabelText('Rank this place')).toBeTruthy();
    expect(queryByText(/top \d+% in San Francisco/)).toBeNull();
  });

  it('shows "regular" framing once the confirmed-visit count crosses the threshold', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    cravesStoreState.saves = [{ ...basePlace(), visited: true, visited_at: '2026-09-01T00:00:00Z', notes: null, visit_confirmation_count: 2 }];
    const { findByText } = renderScreen();

    expect(await findByText("You're a regular here")).toBeTruthy();
    expect(await findByText('Confirmed 2 visits')).toBeTruthy();
  });

  it('renders the threaded reason via the shared DecisionStrip before a visit', async () => {
    mockedUseLocalSearchParams.mockReturnValue({
      id: 'place-1', reason_role: 'best_fit', reason_source: 'craves',
    });
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    const { findByText } = renderScreen();

    expect(await findByText('Best fit')).toBeTruthy();
  });

  it('remembers and shows the persisted save reason on a later visit with no nav params (contract §13)', async () => {
    // No reason_role/reason_source in the nav params this time -- this is
    // a cold return visit, not the original role-bearing navigation.
    mockedUseLocalSearchParams.mockReturnValue({ id: 'place-1' });
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    cravesStoreState.saves = [{
      ...basePlace(), visited: false, visited_at: null, notes: null,
      reason_role: 'wildcard', reason_source: 'craves', visit_confirmation_count: 0,
    }];
    const { findByText } = renderScreen();

    expect(await findByText('Wildcard')).toBeTruthy();
  });

  it('does not show the threaded reason once visited (stop persuading)', async () => {
    mockedUseLocalSearchParams.mockReturnValue({
      id: 'place-1', reason_role: 'best_fit', reason_source: 'craves',
    });
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    cravesStoreState.saves = [{ ...basePlace(), visited: true, visited_at: '2026-09-01T00:00:00Z', notes: null, visit_confirmation_count: 1 }];
    const { findByText, queryByText } = renderScreen();

    await findByText('Already on your list of visits');
    expect(queryByText('Best fit')).toBeNull();
  });

  it('persists the threaded reason on the save itself when saving from a role-bearing arrival', async () => {
    mockedUseLocalSearchParams.mockReturnValue({
      id: 'place-1', reason_role: 'safe_bet', reason_source: 'search',
    });
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    cravesStoreState.addSave.mockResolvedValue(null);
    const { findByLabelText, getByLabelText } = renderScreen();

    await findByLabelText('Get directions');
    fireEvent.press(getByLabelText('Save to Saves'));

    await waitFor(() => expect(cravesStoreState.addSave).toHaveBeenCalled());
    const [, , meta] = cravesStoreState.addSave.mock.calls[0];
    expect(meta).toEqual(expect.objectContaining({
      reason_role: 'safe_bet', reason_source: 'search',
    }));
  });

  it('uses the Foundation Gate HTTPS place link in the native share payload', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    const shareSpy = jest.spyOn(Share, 'share').mockResolvedValue({ action: 'sharedAction' } as any);

    const { findByText } = renderScreen();
    await findByText('Nari');

    expect(mockSetOptions).toHaveBeenCalled();
    const { headerRight } = mockSetOptions.mock.calls[mockSetOptions.mock.calls.length - 1][0];
    const { getByLabelText } = render(headerRight());
    fireEvent.press(getByLabelText('Share this place'));

    expect(shareSpy).toHaveBeenCalledWith(expect.objectContaining({
      message: expect.stringContaining('https://crave.app/place/place-1'),
    }));
    expect(shareSpy).not.toHaveBeenCalledWith(expect.objectContaining({
      message: expect.stringContaining('crave://place/place-1'),
    }));
  });

  it('shows an open-now chip with provenance copy when hours_status is open', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace({
      hours_status: 'open', hours_next_change: '2026-09-09T17:00:00-07:00',
    }));
    const { findByText, findByLabelText } = renderScreen();

    expect(await findByText(/Open now · Closes/)).toBeTruthy();
    expect(await findByText('Hours are based on saved place data and may have changed.')).toBeTruthy();
    expect(await findByLabelText(/Hours are based on saved place data/)).toBeTruthy();
  });

  it('shows a closed chip with the next open time when hours_status is closed', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace({
      hours_status: 'closed', hours_next_change: '2026-09-09T09:00:00-07:00',
    }));
    const { findByText } = renderScreen();

    expect(await findByText(/Closed · Opens/)).toBeTruthy();
  });

  it('shows no hours chip at all when hours_status is unknown', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace({ hours_status: null }));
    const { findByText, queryByText } = renderScreen();

    await findByText('Nari');
    expect(queryByText(/Open now/)).toBeNull();
    expect(queryByText(/Closed/)).toBeNull();
  });

  it('shows an outdoor seating chip when the place has one', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace({ outdoor_seating: 'yes' }));
    const { findByText } = renderScreen();

    expect(await findByText(/Outdoor seating/)).toBeTruthy();
  });

  it('shows no outdoor seating chip when the tag is absent', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace({ outdoor_seating: null }));
    const { findByText, queryByText } = renderScreen();

    await findByText('Nari');
    expect(queryByText(/Outdoor seating/)).toBeNull();
  });

  it('does not imply menu freshness when menu items lack a verification timestamp', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    mockedGetPlaceMenu.mockResolvedValue({
      items: [{ id: 'm1', name: 'Pad Thai', description: null, price: null, category: null }],
      lastVerifiedAt: null,
    } as any);
    const { findByText, queryByText } = renderScreen();

    expect(await findByText('Menu freshness unknown')).toBeTruthy();
    expect(queryByText(/Verified/)).toBeNull();
  });

  it('labels dated menu evidence as updated, not freshly verified', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    mockedGetPlaceMenu.mockResolvedValue({
      items: [{ id: 'm1', name: 'Pad Thai', description: null, price: null, category: null }],
      lastVerifiedAt: '2026-09-10T12:00:00Z',
    } as any);
    const { findByText, queryByText } = renderScreen();

    expect(await findByText(/Menu updated/)).toBeTruthy();
    expect(queryByText(/Verified/)).toBeNull();
  });
});

describe('PlaceDetailScreen — signed-out actions route through the shared auth gate', () => {
  // Previously every one of these was a dead end: a toast ("Sign in to
  // ...") with no sign-in mechanism attached, or (handleSave) no
  // feedback at all. They must now all call the shared contextual
  // auth-gate contract (requestAuthGate) instead.
  beforeEach(() => {
    jest.clearAllMocks();
    cravesStoreState.isSaved.mockReturnValue(false);
    cravesStoreState.saves = [];
    mockedUseAuthStore.mockImplementation((selector: (s: { user: unknown }) => unknown) =>
      selector({ user: null }),
    );
    mockedGetCravesForPlace.mockResolvedValue([]);
    mockedGetPlaceMenu.mockResolvedValue({ items: [], lastVerifiedAt: null } as any);
    mockedFetchPlaceRelationship.mockResolvedValue(baseRelationship());
    mockedUseLocalSearchParams.mockReturnValue({ id: 'place-1' });
  });

  it('gates the plain Save button instead of silently no-op-ing', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    const { findByLabelText } = renderScreen();

    fireEvent.press(await findByLabelText('Save to Saves'));

    expect(mockRequestAuthGate).toHaveBeenCalledWith(
      expect.objectContaining({ actionType: 'save_place', reason: 'save', sourceRoute: '/place/place-1' }),
    );
  });

  it('gates the "Save for tonight" ladder CTA', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace({ lat: null, lng: null }));
    const { findByLabelText } = renderScreen();

    fireEvent.press(await findByLabelText('Save for tonight'));

    expect(mockRequestAuthGate).toHaveBeenCalledWith(
      expect.objectContaining({ actionType: 'save_place', reason: 'save' }),
    );
  });

  it('gates the "Rank it" ladder CTA with a destination back to this rank screen', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    cravesStoreState.saves = [{ ...basePlace(), visited: true, visited_at: '2026-09-01T00:00:00Z', notes: null }];
    const { findByLabelText } = renderScreen();

    fireEvent.press(await findByLabelText('Rank this place'));

    expect(mockRequestAuthGate).toHaveBeenCalledWith(
      expect.objectContaining({
        actionType: 'open_rank_place',
        reason: 'rank',
        destination: '/rank/place-1',
      }),
    );
    expect(mockRouterPush).not.toHaveBeenCalled();
  });

  it('gates adding a photo instead of silently no-op-ing into the picker', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    const { findByLabelText } = renderScreen();

    fireEvent.press(await findByLabelText('Add a photo'));

    expect(mockRequestAuthGate).toHaveBeenCalledWith(
      expect.objectContaining({ actionType: 'add_place_photo' }),
    );
  });

  it('gates suggesting a menu item', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    const { findByLabelText } = renderScreen();

    fireEvent.press(await findByLabelText('Suggest menu items'));

    expect(mockRequestAuthGate).toHaveBeenCalledWith(
      expect.objectContaining({ actionType: 'suggest_menu_item' }),
    );
  });

  it('gates reporting the main photo', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace({ image_ids: ['img-1'] }));
    const { findByLabelText } = renderScreen();

    fireEvent.press(await findByLabelText('Report the main photo'));

    expect(mockRequestAuthGate).toHaveBeenCalledWith(
      expect.objectContaining({ actionType: 'report_place_photo' }),
    );
  });

  it('gates reporting a place issue', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    const { findByLabelText } = renderScreen();

    fireEvent.press(await findByLabelText('Report an issue with this place'));

    expect(mockRequestAuthGate).toHaveBeenCalledWith(
      expect.objectContaining({ actionType: 'report_place_issue' }),
    );
  });
});
