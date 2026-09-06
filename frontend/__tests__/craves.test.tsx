// Recommendation Ledger: Craves-screen instrumentation. surface='craves'
// -- this screen is a *return to already-saved places*, not a discovery
// surface, so an impression/click here is re-engagement with existing
// memory, not fresh taste evidence. Locks in: one bounded, positioned
// impression batch for the primary Saves list on load; a click event
// with the real position on selection; the matched-only Craves/Added
// sections get their own impression+click, positioned within their own
// filtered (matched-id) list, not the raw unfiltered array. Save/unsave
// already goes through cravesStore's certified idempotent path (see
// cravesStore.test.ts) -- not re-tested here.
import React from 'react';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
import CravesScreen from '../app/(tabs)/craves';
import { getCraveItems, getMyPlaceSaves } from '../src/api/crave';
import { logRecommendationEvent, logRecommendationEvents } from '../src/utils/recommendationEventQueue';

const mockPush = jest.fn();
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush }),
}));

const mockUser = { id: 'user-1', email: 'a@b.com' } as any;
jest.mock('../src/stores/authStore', () => ({
  useAuthStore: jest.fn(),
}));
import { useAuthStore } from '../src/stores/authStore';
const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;

const mockLoadSaves = jest.fn();
const mockRemoveSave = jest.fn().mockResolvedValue(null);
let mockStoreState: any = { saves: [], loading: false, error: null, loadSaves: mockLoadSaves, removeSave: mockRemoveSave };
jest.mock('../src/stores/cravesStore', () => {
  const hook: any = () => mockStoreState;
  hook.getState = () => mockStoreState;
  return { useCravesStore: hook };
});

jest.mock('../src/api/crave', () => ({
  getCraveItems: jest.fn(),
  getMyPlaceSaves: jest.fn(),
}));
jest.mock('../src/hooks/usePrefetchPlace', () => ({
  usePrefetchPlace: () => jest.fn(),
}));
// AuthSheet pulls in lib/supabase.ts (real client, needs real env vars
// outside a running app) via its own import chain -- same reason other
// screens' tests stub this component rather than let that chain load.
jest.mock('../src/components/AuthSheet', () => ({
  AuthSheet: () => null,
}));
jest.mock('../src/utils/recommendationEventQueue', () => ({
  logRecommendationEvent: jest.fn(),
  logRecommendationEvents: jest.fn(),
}));
jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  notificationAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'light', Medium: 'medium' },
  NotificationFeedbackType: { Success: 'success', Warning: 'warning', Error: 'error' },
}));

const mockedGetCraveItems = getCraveItems as jest.MockedFunction<typeof getCraveItems>;
const mockedGetMyPlaceSaves = getMyPlaceSaves as jest.MockedFunction<typeof getMyPlaceSaves>;
const mockedLogOne = logRecommendationEvent as jest.Mock;
const mockedLogMany = logRecommendationEvents as jest.Mock;

const SAVED_PLACES = [
  { id: 'p0', name: 'p0', rank_percentile: 0.9, city_id: 'city-sf' },
  { id: 'p1', name: 'p1', rank_percentile: 0.5, city_id: 'city-sf' },
] as any;

function renderScreen() {
  return render(<CravesScreen />);
}

describe('CravesScreen — Recommendation Ledger instrumentation', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedUseAuthStore.mockImplementation((selector: (s: { user: unknown }) => unknown) =>
      selector({ user: mockUser }),
    );
    mockStoreState = { saves: [], loading: false, error: null, loadSaves: mockLoadSaves, removeSave: mockRemoveSave };
    mockLoadSaves.mockImplementation(async () => {
      mockStoreState = { ...mockStoreState, saves: SAVED_PLACES };
    });
    mockedGetCraveItems.mockResolvedValue([]);
    mockedGetMyPlaceSaves.mockResolvedValue([]);
  });

  it('does not describe a failed craves request as an empty account, when saves and placeSaves are also empty', async () => {
    // Confirmed real bug: cravesError is tracked and correctly rendered
    // in the FlashList's own ListFooterComponent, but the top-level
    // "true empty" gate never checked it -- a craves-fetch failure with
    // zero saves/placeSaves rendered "Start your food memory" instead of
    // the real error.
    mockLoadSaves.mockImplementation(async () => {
      mockStoreState = { ...mockStoreState, saves: [] };
    });
    mockedGetCraveItems.mockRejectedValue(new Error('network'));

    const { findByText, queryByText } = renderScreen();

    expect(await findByText("Couldn't load Craves right now.")).toBeTruthy();
    expect(queryByText('Start your food memory')).toBeNull();
  });

  it('logs one bounded, positioned impression batch for the Saves list on load', async () => {
    renderScreen();

    await waitFor(() => expect(mockedLogMany).toHaveBeenCalled());

    const savesBatch = mockedLogMany.mock.calls.find((c) =>
      c[0].some((e: any) => e.place_id === 'p0'),
    )?.[0];
    expect(savesBatch).toBeDefined();
    expect(savesBatch).toHaveLength(2);
    expect(savesBatch[0]).toMatchObject({
      surface: 'craves', event_type: 'impression', place_id: 'p0', position: 0,
      rank_percentile: 0.9, city_id: 'city-sf',
    });
    expect(savesBatch[1]).toMatchObject({ place_id: 'p1', position: 1 });
  });

  it('logs a click with the real position on selecting a saved place', async () => {
    const { getByLabelText } = renderScreen();
    await waitFor(() => expect(mockedLogMany).toHaveBeenCalled());

    // rank_percentile 0.5 -> 'solid' tier ("Worth Knowing"), per scoring.ts's
    // tierFromPercentile bands.
    fireEvent.press(getByLabelText('p1, Restaurant, Worth Knowing'));

    expect(mockedLogOne).toHaveBeenCalledWith(
      expect.objectContaining({
        surface: 'craves', event_type: 'click', place_id: 'p1', position: 1,
        rank_percentile: 0.5, city_id: 'city-sf',
      }),
    );
    expect(mockPush).toHaveBeenCalledWith('/place/p1');
  });

  it('only counts matched Craves items as impressions/clicks, positioned within the matched-only list', async () => {
    mockedGetCraveItems.mockResolvedValue([
      { id: 'c0', url: 'u0', source_type: 'tiktok', parsed_place_name: 'Unmatched', matched_place_id: null, match_confidence: null, status: 'pending', created_at: '', thumbnail_url: null, author_name: null },
      { id: 'c1', url: 'u1', source_type: 'tiktok', parsed_place_name: 'Matched One', matched_place_id: 'm1', match_confidence: 0.9, status: 'matched', created_at: '', thumbnail_url: null, author_name: null },
    ] as any);

    const { getByLabelText } = renderScreen();
    await waitFor(() =>
      expect(mockedLogMany).toHaveBeenCalledWith(
        expect.arrayContaining([expect.objectContaining({ place_id: 'm1', position: 0, surface: 'craves' })]),
      ),
    );
    // The unmatched item never appears in any logged batch -- no place_id to log.
    expect(mockedLogMany.mock.calls.some((c) => c[0].some((e: any) => e.place_id === 'c0'))).toBe(false);

    fireEvent.press(getByLabelText('Open matched place for Matched One'));
    expect(mockedLogOne).toHaveBeenCalledWith(
      expect.objectContaining({ surface: 'craves', event_type: 'click', place_id: 'm1', position: 0 }),
    );
    expect(mockPush).toHaveBeenCalledWith('/place/m1');
  });
});
