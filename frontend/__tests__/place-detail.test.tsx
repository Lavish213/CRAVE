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
import { render, waitFor, fireEvent } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import PlaceDetailScreen from '../app/place/[id]';
import { fetchPlaceDetail } from '../src/api/places';
import { getPlaceMenu } from '../src/api/menu';
import { getCravesForPlace } from '../src/api/crave';
import { fetchMyRankings, fetchFriendRankings } from '../src/api/social';

jest.mock('expo-router', () => ({
  useLocalSearchParams: () => ({ id: 'place-1' }),
  useNavigation: () => ({ setOptions: jest.fn() }),
  useRouter: () => ({ push: jest.fn() }),
}));
jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  notificationAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'light', Medium: 'medium' },
  NotificationFeedbackType: { Success: 'success', Warning: 'warning', Error: 'error' },
}));
jest.mock('../src/api/places', () => ({ fetchPlaceDetail: jest.fn() }));
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
jest.mock('../src/components/MenuSubmissionSheet', () => ({ MenuSubmissionSheet: () => null }));

import { useAuthStore } from '../src/stores/authStore';
const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;
const cravesStoreState = (jest.requireMock('../src/stores/cravesStore') as any).__state;

// Stable reference across renders -- a fresh object literal returned from
// useAuthStore's mock every call would retrigger the friendRankings
// effect (keyed on [id, user]) forever, since it'd look like a new user
// on every render.
const mockAuthUser = { id: 'user-1' };

const mockedFetchPlaceDetail = fetchPlaceDetail as jest.MockedFunction<typeof fetchPlaceDetail>;
const mockedGetPlaceMenu = getPlaceMenu as jest.MockedFunction<typeof getPlaceMenu>;
const mockedGetCravesForPlace = getCravesForPlace as jest.MockedFunction<typeof getCravesForPlace>;

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
  });

  it('renders identity as a header and "why this fits" with a real percentile', async () => {
    mockedFetchPlaceDetail.mockResolvedValue(basePlace());
    const { getByText, findByText } = renderScreen();

    await findByText('Nari');
    expect(getByText('Nari').props.accessibilityRole).toBe('header');
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
