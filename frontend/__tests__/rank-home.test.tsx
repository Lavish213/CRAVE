import React from 'react';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import RankHomeScreen from '../app/rank-home';
import { fetchRankQueue } from '../src/api/rankHome';
import { fetchMyRankings } from '../src/api/social';
import { useAuthStore } from '../src/stores/authStore';
import { requestAuthGate } from '../src/stores/authGateStore';

const mockPush = jest.fn();
jest.mock('expo-router', () => ({ useRouter: () => ({ push: mockPush }) }));
jest.mock('../src/api/rankHome', () => ({ fetchRankQueue: jest.fn() }));
jest.mock('../src/api/social', () => ({ fetchMyRankings: jest.fn() }));
jest.mock('../src/stores/authStore', () => ({ useAuthStore: jest.fn() }));
jest.mock('../src/stores/authGateStore', () => ({ requestAuthGate: jest.fn() }));

const mockedAuth = useAuthStore as unknown as jest.Mock;
const mockedQueue = fetchRankQueue as jest.MockedFunction<typeof fetchRankQueue>;
const mockedRankings = fetchMyRankings as jest.MockedFunction<typeof fetchMyRankings>;
const mockedGate = requestAuthGate as jest.MockedFunction<typeof requestAuthGate>;

function renderScreen() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>
      <RankHomeScreen />
    </QueryClientProvider>,
  );
}

describe('RankHomeScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedAuth.mockImplementation((selector: (state: { user: { id: string } | null }) => unknown) =>
      selector({ user: { id: 'user-1' } }),
    );
    mockedQueue.mockResolvedValue([]);
    mockedRankings.mockResolvedValue([]);
  });

  it('gates the signed-out screen through the shared auth gate', () => {
    mockedAuth.mockImplementation((selector: (state: { user: null }) => unknown) => selector({ user: null }));
    const { getByText } = renderScreen();

    fireEvent.press(getByText('Sign in'));
    expect(mockedGate).toHaveBeenCalledWith(expect.objectContaining({
      actionType: 'open_rank_home',
      reason: 'rank',
      sourceRoute: '/rank-home',
    }));
  });

  it('shows eligible visits before ranked places and routes queue rows to comparison', async () => {
    mockedQueue.mockResolvedValue([
      {
        place_id: 'queue-1',
        name: 'Queue Place',
        visited_at: new Date().toISOString(),
        evidence_tier: 'declared',
        evidence_source: 'save_memory',
        primary_image_url: null,
        city_id: 'city-1',
      },
    ]);
    mockedRankings.mockResolvedValue([
      { place_id: 'rank-1', name: 'Loved Place', tier: 'liked', rank_score: 9.4, note: null, tags: null, visited_at: null, primary_image_url: null, city_id: 'city-1' },
    ]);

    const { findByText, getByLabelText } = renderScreen();
    expect(await findByText('Waiting to be ranked')).toBeTruthy();
    expect(await findByText('Your ranked places')).toBeTruthy();

    fireEvent.press(getByLabelText(/Rank Queue Place/));
    expect(mockPush).toHaveBeenCalledWith('/rank/queue-1');
  });

  it('derives Elite/Love/Good deterministically and excludes disliked rows', async () => {
    mockedRankings.mockResolvedValue([
      { place_id: 'elite-1', name: 'Elite Place', tier: 'liked', rank_score: 8.31, note: null, tags: null, visited_at: null, primary_image_url: null, city_id: 'city-1' },
      { place_id: 'love-1', name: 'Love Place', tier: 'liked', rank_score: 8.3, note: null, tags: null, visited_at: null, primary_image_url: null, city_id: 'city-1' },
      { place_id: 'good-1', name: 'Good Place', tier: 'fine', rank_score: 5.1, note: null, tags: null, visited_at: null, primary_image_url: null, city_id: 'city-1' },
      { place_id: 'nope-1', name: 'Not For Me Place', tier: 'disliked', rank_score: 1.1, note: null, tags: null, visited_at: null, primary_image_url: null, city_id: 'city-1' },
    ]);

    const { findByText, queryByText } = renderScreen();
    expect(await findByText('Elite')).toBeTruthy();
    expect(await findByText('Love')).toBeTruthy();
    expect(await findByText('Good')).toBeTruthy();
    expect(await findByText('Elite Place')).toBeTruthy();
    expect(await findByText('Love Place')).toBeTruthy();
    expect(await findByText('Good Place')).toBeTruthy();
    expect(queryByText('Not For Me Place')).toBeNull();
    expect(queryByText('8.31')).toBeNull();
    expect(queryByText('8.3')).toBeNull();
    expect(queryByText('5.1')).toBeNull();
  });

  it('shows a specific empty action when no visits or rankings exist', async () => {
    const { findByText } = renderScreen();
    expect(await findByText('Your Rank starts after a real visit')).toBeTruthy();
    fireEvent.press(await findByText('Browse places'));
    expect(mockPush).toHaveBeenCalledWith('/');
  });

  it('keeps usable ranked data visible when only the queue request fails', async () => {
    mockedQueue.mockRejectedValue(new Error('queue offline'));
    mockedRankings.mockResolvedValue([
      { place_id: 'rank-1', name: 'Loved Place', tier: 'liked', rank_score: 8.8, note: null, tags: null, visited_at: null, primary_image_url: null, city_id: 'city-1' },
    ]);

    const { findByText } = renderScreen();
    await waitFor(() => expect(mockedQueue).toHaveBeenCalled());
    expect(await findByText("Couldn't load places waiting to be ranked")).toBeTruthy();
    expect(await findByText('Loved Place')).toBeTruthy();
  });
});
