import React from 'react';
import { Alert } from 'react-native';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import CravesScreen from '../app/(tabs)/craves';
import {
  CraveItem, getCraveItems, getMyPlaceSaves, PlaceSaveItem, fetchCravesReasoned,
} from '../src/api/crave';
import { SavedPlace } from '../src/api/saves';
import { logRecommendationEvent, logRecommendationEvents } from '../src/utils/recommendationEventQueue';

interface MockFlashListProps {
  data: unknown[];
  renderItem: (args: { item: unknown; index: number }) => React.ReactNode;
  ListHeaderComponent?: React.ReactNode;
  onViewableItemsChanged?: (info: {
    viewableItems: Array<{
      item: unknown;
      key: string;
      index: number;
      isViewable: boolean;
      timestamp: number;
    }>;
  }) => void;
}

let mockFlashListProps: MockFlashListProps | null = null;
jest.mock('@shopify/flash-list', () => {
  const ReactModule = require('react');
  const { View } = require('react-native');
  return {
    FlashList: (props: MockFlashListProps) => {
      mockFlashListProps = props;
      return ReactModule.createElement(
        View,
        { testID: 'mock-flash-list' },
        props.ListHeaderComponent,
        ...props.data.map((item, index) => props.renderItem({ item, index })),
      );
    },
  };
});

const mockPush = jest.fn();
jest.mock('expo-router', () => ({ useRouter: () => ({ push: mockPush }) }));

const mockUser = { id: 'user-1', email: 'a@b.com' };
jest.mock('../src/stores/authStore', () => ({ useAuthStore: jest.fn() }));
import { useAuthStore } from '../src/stores/authStore';
const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;

const mockLoadSaves = jest.fn();
const mockRemoveSave = jest.fn().mockResolvedValue(null);
interface MockCravesStoreState {
  saves: SavedPlace[];
  loading: boolean;
  error: string | null;
  loadSaves: typeof mockLoadSaves;
  removeSave: typeof mockRemoveSave;
}
let mockStoreState: MockCravesStoreState = {
  saves: [], loading: false, error: null, loadSaves: mockLoadSaves, removeSave: mockRemoveSave,
};
jest.mock('../src/stores/cravesStore', () => {
  const hook = () => mockStoreState;
  Object.assign(hook, { getState: () => mockStoreState });
  return { useCravesStore: hook };
});

jest.mock('../src/api/crave', () => ({
  getCraveItems: jest.fn(),
  getMyPlaceSaves: jest.fn(),
  fetchCravesReasoned: jest.fn(),
}));
jest.mock('../src/hooks/usePrefetchPlace', () => ({ usePrefetchPlace: () => jest.fn() }));
jest.mock('../src/hooks/useLocation', () => ({ useLocation: jest.fn(() => null) }));
import { useLocation } from '../src/hooks/useLocation';
const mockedUseLocation = useLocation as jest.Mock;
jest.mock('../src/components/AuthSheet', () => ({ AuthSheet: () => null }));
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
const mockedFetchCravesReasoned = fetchCravesReasoned as jest.MockedFunction<typeof fetchCravesReasoned>;
const mockedLogOne = logRecommendationEvent as jest.Mock;
const mockedLogMany = logRecommendationEvents as jest.Mock;

const SAVED_PLACES = [
  { id: 'p0', name: 'p0', rank_percentile: 0.9, city_id: 'city-sf', visited: false, visited_at: null, notes: null },
  { id: 'p1', name: 'p1', rank_percentile: 0.5, city_id: 'city-sf', visited: false, visited_at: null, notes: null },
] as unknown as SavedPlace[];

function makeSavedPlace(overrides: Record<string, unknown> = {}): SavedPlace {
  return {
    id: 'cluster-place', name: 'Cluster Place', rank_percentile: 0.6, city_id: 'city-sf',
    visited: false, visited_at: null, notes: null, category: null, lat: null, lng: null,
    ...overrides,
  } as unknown as SavedPlace;
}

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CravesScreen />
    </QueryClientProvider>,
  );
}

function exposeAllRows() {
  if (!mockFlashListProps?.onViewableItemsChanged) throw new Error('FlashList viewability handler missing');
  act(() => {
    mockFlashListProps!.onViewableItemsChanged!({
      viewableItems: mockFlashListProps!.data.map((item, index) => ({
        item,
        key: `row-${index}`,
        index,
        isViewable: true,
        timestamp: Date.now(),
      })),
    });
  });
}

function makeCrave(overrides: Partial<CraveItem> = {}): CraveItem {
  return {
    id: 'c0', url: 'u0', source_type: 'tiktok', parsed_place_name: 'Place',
    matched_place_id: null, match_confidence: null, status: 'pending', created_at: '',
    thumbnail_url: null, author_name: null, ...overrides,
  };
}

function makeReasonedCard(overrides: { id?: string; name?: string; rank_percentile?: number; role?: 'best_fit' | 'safe_bet' | 'wildcard' } = {}) {
  return {
    place: {
      id: overrides.id ?? 'r0', name: overrides.name ?? 'Reasoned Pick',
      rank_percentile: overrides.rank_percentile ?? 0.95, city_id: 'city-sf',
    } as unknown as import('../src/api/places').PlaceOut,
    role: overrides.role ?? 'best_fit',
    reason_codes: [],
  };
}

function pressAlertButton(buttonText: string) {
  const call = (Alert.alert as jest.Mock).mock.calls[(Alert.alert as jest.Mock).mock.calls.length - 1];
  const buttons = call[2] as { text: string; onPress?: () => void }[];
  const button = buttons.find((b) => b.text === buttonText);
  button?.onPress?.();
}

function makePlaceSave(overrides: Partial<PlaceSaveItem> = {}): PlaceSaveItem {
  return {
    id: 'a0', place_name: 'Typed Place', source_platform: null, source_url: null,
    place_id: null, lat: null, lng: null, resolution_status: 'pending', created_at: null,
    resolved_at: null, ...overrides,
  };
}

describe('CravesScreen — async truth and exposure instrumentation', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFlashListProps = null;
    mockedUseAuthStore.mockImplementation((selector: (s: { user: typeof mockUser }) => unknown) =>
      selector({ user: mockUser }),
    );
    mockStoreState = {
      saves: [], loading: false, error: null, loadSaves: mockLoadSaves, removeSave: mockRemoveSave,
    };
    mockLoadSaves.mockImplementation(async () => {
      mockStoreState = { ...mockStoreState, saves: SAVED_PLACES };
    });
    mockedGetCraveItems.mockResolvedValue([]);
    mockedGetMyPlaceSaves.mockResolvedValue([]);
    mockedFetchCravesReasoned.mockResolvedValue({ cards: [], degraded: true });
    mockedUseLocation.mockReturnValue(null);
    jest.spyOn(Alert, 'alert').mockImplementation(() => {});
  });

  it('does not describe a failed Craves request as an empty account', async () => {
    mockLoadSaves.mockImplementation(async () => {
      mockStoreState = { ...mockStoreState, saves: [] };
    });
    mockedGetCraveItems.mockRejectedValue(new Error('network'));

    const { findByText, queryByText } = renderScreen();
    expect(await findByText(/Couldn't load Craves right now/)).toBeTruthy();
    expect(queryByText('Start your food memory')).toBeNull();
  });

  it('does not describe a failed manual Added request as an empty account', async () => {
    mockLoadSaves.mockImplementation(async () => {
      mockStoreState = { ...mockStoreState, saves: [] };
    });
    mockedGetMyPlaceSaves.mockRejectedValue(new Error('network'));

    const { findByText, queryByText } = renderScreen();
    expect(await findByText(/Couldn't load added places right now/)).toBeTruthy();
    expect(queryByText('Start your food memory')).toBeNull();
  });

  it('shows true empty only after both secondary resources successfully settle for the current user', async () => {
    mockLoadSaves.mockImplementation(async () => {
      mockStoreState = { ...mockStoreState, saves: [] };
    });

    const { findByText } = renderScreen();
    expect(await findByText('Start your food memory')).toBeTruthy();
    expect(mockedGetCraveItems).toHaveBeenCalledTimes(1);
    expect(mockedGetMyPlaceSaves).toHaveBeenCalledTimes(1);
  });

  it('does not log fetched Saves until their rows are actually exposed', async () => {
    renderScreen();
    await waitFor(() => expect(mockFlashListProps?.data.some(
      (row) => typeof row === 'object' && row !== null && (row as { kind?: string }).kind === 'save',
    )).toBe(true));

    expect(mockedLogMany).not.toHaveBeenCalled();
    exposeAllRows();

    expect(mockedLogMany).toHaveBeenCalledTimes(1);
    const batch = mockedLogMany.mock.calls[0][0];
    expect(batch).toEqual(expect.arrayContaining([
      expect.objectContaining({ place_id: 'p0', position: 0, rank_percentile: 0.9, city_id: 'city-sf' }),
      expect.objectContaining({ place_id: 'p1', position: 1, rank_percentile: 0.5, city_id: 'city-sf' }),
    ]));
  });

  it('deduplicates a row when viewability fires repeatedly', async () => {
    renderScreen();
    await waitFor(() => expect(mockFlashListProps?.data.length).toBeGreaterThan(0));
    exposeAllRows();
    const calls = mockedLogMany.mock.calls.length;
    exposeAllRows();
    expect(mockedLogMany).toHaveBeenCalledTimes(calls);
  });

  it('logs a saved-place click with the same real section position', async () => {
    const { getByLabelText } = renderScreen();
    await waitFor(() => expect(mockFlashListProps?.data.length).toBeGreaterThan(0));
    exposeAllRows();

    fireEvent.press(getByLabelText('p1, Restaurant, Worth Knowing'));
    expect(mockedLogOne).toHaveBeenCalledWith(expect.objectContaining({
      surface: 'craves', event_type: 'click', place_id: 'p1', position: 1,
      rank_percentile: 0.5, city_id: 'city-sf',
    }));
    expect(mockPush).toHaveBeenCalledWith('/place/p1');
  });

  it('only exposes matched shared Craves and preserves matched-only position', async () => {
    mockedGetCraveItems.mockResolvedValue([
      makeCrave({ id: 'c0', parsed_place_name: 'Unmatched' }),
      makeCrave({ id: 'c1', parsed_place_name: 'Matched One', matched_place_id: 'm1', match_confidence: 0.9, status: 'matched' }),
    ]);

    const { getByLabelText } = renderScreen();
    await waitFor(() => expect(getByLabelText('Open matched place for Matched One')).toBeTruthy());
    expect(mockedLogMany).not.toHaveBeenCalled();
    exposeAllRows();

    const allEvents = mockedLogMany.mock.calls.flatMap((call) => call[0]);
    expect(allEvents).toContainEqual(expect.objectContaining({ place_id: 'm1', position: 0 }));
    expect(allEvents.some((event: { place_id?: string | null }) => event.place_id === 'c0')).toBe(false);

    fireEvent.press(getByLabelText('Open matched place for Matched One'));
    expect(mockedLogOne).toHaveBeenCalledWith(expect.objectContaining({ place_id: 'm1', position: 0 }));
  });

  it('exposes a matched manual Added row only after viewability', async () => {
    mockedGetMyPlaceSaves.mockResolvedValue([
      makePlaceSave({ id: 'a0', place_name: 'Unmatched Added' }),
      makePlaceSave({ id: 'a1', place_name: 'Matched Added', place_id: 'added-place', resolution_status: 'matched' }),
    ]);

    const { getByLabelText } = renderScreen();
    await waitFor(() => expect(getByLabelText('Open matched place for Matched Added')).toBeTruthy());
    expect(mockedLogMany).not.toHaveBeenCalled();
    exposeAllRows();

    expect(mockedLogMany.mock.calls.flatMap((call) => call[0])).toContainEqual(
      expect.objectContaining({ place_id: 'added-place', position: 0 }),
    );
  });

  it('shows the reasoned subset first, above the full saved list (Craves Screen Contract §5/§6)', async () => {
    mockedFetchCravesReasoned.mockResolvedValue({
      cards: [makeReasonedCard()],
      degraded: true,
    });

    const { findByText } = renderScreen();
    expect(await findByText('Try one of these')).toBeTruthy();
    expect(await findByText('Reasoned Pick')).toBeTruthy();
    expect(await findByText('All saves')).toBeTruthy();
  });

  it('logs a reasoned-card click with its decision role', async () => {
    mockedFetchCravesReasoned.mockResolvedValue({
      cards: [makeReasonedCard()],
      degraded: true,
    });

    const { findByLabelText } = renderScreen();
    fireEvent.press(await findByLabelText('Reasoned Pick, Restaurant, CRAVE Pick'));

    expect(mockedLogOne).toHaveBeenCalledWith(expect.objectContaining({
      surface: 'craves', event_type: 'click', place_id: 'r0', position: 0, decision_role: 'best_fit',
    }));
    expect(mockPush).toHaveBeenCalledWith('/place/r0');
  });

  it('shows an honest "nothing fits right now" message when the reasoned subset is empty but saves exist', async () => {
    mockedFetchCravesReasoned.mockResolvedValue({ cards: [], degraded: true });
    const { findByText } = renderScreen();
    expect(await findByText(/nothing in your craves fits right now/i)).toBeTruthy();
  });

  it('requires confirmation before removing a save (Craves Screen Contract §17)', async () => {
    const { getByLabelText } = renderScreen();
    await waitFor(() => expect(mockFlashListProps?.data.length).toBeGreaterThan(0));

    fireEvent.press(getByLabelText('Remove p0 from saves'));
    expect(mockRemoveSave).not.toHaveBeenCalled();
    expect(Alert.alert).toHaveBeenCalledWith(
      'Remove p0?',
      expect.stringContaining('removes it from your Craves'),
      expect.any(Array),
    );

    pressAlertButton('Remove');
    await waitFor(() => expect(mockRemoveSave).toHaveBeenCalledWith('p0', 'user-1', expect.anything()));
  });

  it('does not remove a save when the confirmation is cancelled', async () => {
    const { getByLabelText } = renderScreen();
    await waitFor(() => expect(mockFlashListProps?.data.length).toBeGreaterThan(0));

    fireEvent.press(getByLabelText('Remove p0 from saves'));
    pressAlertButton('Cancel');
    expect(mockRemoveSave).not.toHaveBeenCalled();
  });

  it('does not show automatic clusters for a small saved pool (Craves Screen Contract §6)', async () => {
    const { findByText, queryByText } = renderScreen();
    expect(await findByText('All saves')).toBeTruthy();
    expect(queryByText('Ramen')).toBeNull();
  });

  it('clusters by cuisine once the saved pool is large and varied enough', async () => {
    mockLoadSaves.mockImplementation(async () => {
      mockStoreState = {
        ...mockStoreState,
        saves: [
          makeSavedPlace({ id: 'ramen0', name: 'Ramen A', category: 'Ramen' }),
          makeSavedPlace({ id: 'ramen1', name: 'Ramen B', category: 'Ramen' }),
          makeSavedPlace({ id: 'ramen2', name: 'Ramen C', category: 'Ramen' }),
          makeSavedPlace({ id: 'taco0', name: 'Taco A', category: 'Tacos' }),
          makeSavedPlace({ id: 'taco1', name: 'Taco B', category: 'Tacos' }),
          makeSavedPlace({ id: 'pizza0', name: 'Pizza A', category: 'Pizza' }),
        ],
      };
    });

    const { findByText, findAllByText } = renderScreen();
    expect(await findByText('3 of your saves')).toBeTruthy();
    // Appears twice by design: once in the cluster, once in the always-
    // reachable full list below it (contract §6 -- clusters are curated
    // views into the pool, not a filter on the exhaustive list).
    expect((await findAllByText('Ramen A')).length).toBe(2);
    expect(await findByText('All saves')).toBeTruthy();
  });

  it('logs a cluster-card impression and click with its own position', async () => {
    mockLoadSaves.mockImplementation(async () => {
      mockStoreState = {
        ...mockStoreState,
        saves: [
          makeSavedPlace({ id: 'ramen0', name: 'Ramen A', category: 'Ramen' }),
          makeSavedPlace({ id: 'ramen1', name: 'Ramen B', category: 'Ramen' }),
          makeSavedPlace({ id: 'ramen2', name: 'Ramen C', category: 'Ramen' }),
          makeSavedPlace({ id: 'taco0', name: 'Taco A', category: 'Tacos' }),
          makeSavedPlace({ id: 'taco1', name: 'Taco B', category: 'Tacos' }),
          makeSavedPlace({ id: 'pizza0', name: 'Pizza A', category: 'Pizza' }),
        ],
      };
    });

    const { findByText, getAllByLabelText } = renderScreen();
    await findByText('3 of your saves');
    exposeAllRows();

    const allEvents = mockedLogMany.mock.calls.flatMap((call) => call[0]);
    expect(allEvents).toContainEqual(expect.objectContaining({ place_id: 'ramen0', position: 0 }));

    // The cluster's own card renders first, ahead of its duplicate in the
    // full list below -- press that one to exercise the cluster's own
    // (per-cluster, not global-list) position in the logged click.
    fireEvent.press(getAllByLabelText('Ramen A, Ramen, Worth Knowing')[0]);
    expect(mockedLogOne).toHaveBeenCalledWith(expect.objectContaining({
      surface: 'craves', event_type: 'click', place_id: 'ramen0', position: 0,
    }));
  });

  it('clusters "Near Home" saves once the user\'s location is known', async () => {
    mockedUseLocation.mockReturnValue({ lat: 37.7749, lng: -122.4194 });
    mockLoadSaves.mockImplementation(async () => {
      mockStoreState = {
        ...mockStoreState,
        saves: [
          makeSavedPlace({ id: 'near0', name: 'Near A', lat: 37.775, lng: -122.4194 }),
          makeSavedPlace({ id: 'near1', name: 'Near B', lat: 37.7751, lng: -122.4194 }),
          makeSavedPlace({ id: 'near2', name: 'Near C', lat: 37.7752, lng: -122.4194 }),
          makeSavedPlace({ id: 'far0', name: 'Far A', lat: 37.7749, lng: -121.0 }),
          makeSavedPlace({ id: 'far1', name: 'Far B', lat: 37.7749, lng: -121.0 }),
          makeSavedPlace({ id: 'far2', name: 'Far C', lat: 37.7749, lng: -121.0 }),
        ],
      };
    });

    const { findByText } = renderScreen();
    expect(await findByText('Near Home')).toBeTruthy();
    expect(await findByText('Worth the Drive')).toBeTruthy();
  });
});
