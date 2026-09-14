import React from 'react';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ActivityScreen from '../app/activity';
import { fetchMyActivity } from '../src/api/social';
import { requestAuthGate } from '../src/stores/authGateStore';

const mockPush = jest.fn();
let mockUser: { id: string } | null = { id: 'me' };

jest.mock('expo-router', () => ({ useRouter: () => ({ push: mockPush }) }));
jest.mock('../src/stores/authStore', () => ({
  useAuthStore: (selector: (state: { user: typeof mockUser }) => unknown) => selector({ user: mockUser }),
}));
jest.mock('../src/stores/authGateStore', () => ({ requestAuthGate: jest.fn() }));
jest.mock('../src/api/social', () => ({ fetchMyActivity: jest.fn() }));
jest.mock('@shopify/flash-list', () => {
  const ReactNative = require('react-native');
  return {
    FlashList: ({ data, renderItem, ListHeaderComponent }: any) => (
      <ReactNative.View>
        {ListHeaderComponent}
        {data.map((item: any, index: number) => (
          <ReactNative.View key={item.id}>{renderItem({ item, index })}</ReactNative.View>
        ))}
      </ReactNative.View>
    ),
  };
});

const mockedFetch = fetchMyActivity as jest.MockedFunction<typeof fetchMyActivity>;
const mockedGate = requestAuthGate as jest.MockedFunction<typeof requestAuthGate>;

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ActivityScreen />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  mockUser = { id: 'me' };
});

it('gates signed-out activity without issuing a request', () => {
  mockUser = null;
  const { getByLabelText } = renderScreen();
  fireEvent.press(getByLabelText('Sign in'));
  expect(mockedFetch).not.toHaveBeenCalled();
  expect(mockedGate).toHaveBeenCalledWith(expect.objectContaining({ destination: '/activity' }));
});

it('renders only factual backend events and opens ranked places', async () => {
  mockedFetch.mockResolvedValue([{
    id: 'event-1', user_id: 'me', actor: null, event_type: 'ranked_place',
    place_id: 'place-1', place_name: 'Saffron', place_image_url: null,
    target_user_id: null, target_user: null, payload: { tier: 'liked', score: 8 },
    created_at: new Date().toISOString(),
  }]);
  const { findByLabelText } = renderScreen();
  fireEvent.press(await findByLabelText('You ranked Saffron'));
  expect(mockedFetch).toHaveBeenCalledWith(30, 0, expect.any(AbortSignal));
  expect(mockPush).toHaveBeenCalledWith('/place/place-1');
});

it('distinguishes a failed load from an empty history', async () => {
  // A real backend error (has a `response`) falls back to this screen's
  // own generic copy -- classification now goes through the shared
  // errorMessageFor/Foundation Gate taxonomy instead of a hardcoded
  // string, but only the two specifically-classified kinds (rate-limited,
  // offline) override it. See the next test for that offline case.
  mockedFetch.mockRejectedValue({ response: { status: 500 } });
  const { findByText } = renderScreen();
  expect(await findByText("Couldn't load your activity")).toBeTruthy();
});

it('shows offline-specific copy for a genuine connectivity failure, not the generic message', async () => {
  // Real gap this closes: this screen used to render the exact same
  // "Couldn't load your activity" for a real backend error and a request
  // that never reached the backend at all -- no response means offline,
  // same classification every other errorMessageFor caller in the app
  // already gets.
  mockedFetch.mockRejectedValue(new Error('offline'));
  const { findByText } = renderScreen();
  expect(await findByText("Can't reach CRAVE — check your connection.")).toBeTruthy();
});

it('shows an honest empty state', async () => {
  mockedFetch.mockResolvedValue([]);
  const { findByText } = renderScreen();
  await waitFor(() => expect(findByText('No activity yet')).resolves.toBeTruthy());
});
