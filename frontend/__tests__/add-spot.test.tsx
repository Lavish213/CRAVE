// add-spot screen (app/add-spot.tsx) — first dedicated coverage. Locks
// in: the locating -> searching -> ready state machine, the
// unauthenticated/denied/error branches, already-in-CRAVE vs. new-spot
// card actions, the confirm success/failure paths, and the
// account-switch guard that resets confirmedIds/confirmingId (mirrors
// craves.tsx's own account-generation pattern).
import React from 'react';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
import * as Location from 'expo-location';
import AddSpotScreen from '../app/add-spot';
import { useAuthStore } from '../src/stores/authStore';
import { NearbyCandidate, confirmNewSpot, searchNearby } from '../src/api/nearby';

const mockPush = jest.fn();
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush }),
}));
jest.mock('../src/stores/authStore', () => ({
  useAuthStore: jest.fn(),
}));
jest.mock('../src/api/nearby', () => ({
  searchNearby: jest.fn(),
  confirmNewSpot: jest.fn(),
}));
jest.mock('expo-location', () => ({
  requestForegroundPermissionsAsync: jest.fn(),
  getCurrentPositionAsync: jest.fn(),
  Accuracy: { High: 4 },
}));
jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  notificationAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'light' },
  NotificationFeedbackType: { Success: 'success', Error: 'error' },
}));
const mockToastShow = jest.fn();
jest.mock('../src/hooks/useToast', () => ({
  useToast: (selector: (s: { show: (msg: string) => void }) => unknown) =>
    selector({ show: mockToastShow }),
}));
jest.mock('../src/components/AuthSheet', () => {
  const { Text } = require('react-native');
  return {
    AuthSheet: ({ visible }: { visible: boolean }) =>
      visible ? <Text testID="auth-sheet-visible">auth</Text> : null,
  };
});

const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;
const mockedSearchNearby = searchNearby as jest.MockedFunction<typeof searchNearby>;
const mockedConfirmNewSpot = confirmNewSpot as jest.MockedFunction<typeof confirmNewSpot>;
const mockedRequestPermission = Location.requestForegroundPermissionsAsync as jest.Mock;
const mockedGetPosition = Location.getCurrentPositionAsync as jest.Mock;

function setAuth(user: { id: string } | null, loading = false) {
  mockedUseAuthStore.mockImplementation((selector: (s: unknown) => unknown) =>
    selector({ user, loading }),
  );
}

function makeCandidate(overrides: Partial<NearbyCandidate> = {}): NearbyCandidate {
  return {
    external_id: 'ext-1', name: 'Tasty Spot', address: '123 Main St', lat: 37.7, lng: -122.4,
    category_hint: 'Cafe', distance_m: 42, already_in_crave: false, place_id: null,
    ...overrides,
  };
}

describe('AddSpotScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedRequestPermission.mockResolvedValue({ status: 'granted' });
    mockedGetPosition.mockResolvedValue({ coords: { latitude: 37.7749, longitude: -122.4194 } });
    mockedSearchNearby.mockResolvedValue([]);
  });

  it('shows an unauthenticated prompt and opens AuthSheet, without ever requesting location', async () => {
    setAuth(null);
    const { findByText, findByTestId } = render(<AddSpotScreen />);

    expect(await findByText('Sign in to add a new spot.')).toBeTruthy();
    expect(mockedRequestPermission).not.toHaveBeenCalled();

    fireEvent.press(await findByText('Sign in'));
    expect(await findByTestId('auth-sheet-visible')).toBeTruthy();
  });

  it('stays on the locating state while auth is still hydrating, rather than treating it as signed out', () => {
    setAuth(null, true);
    const { getByText, queryByText } = render(<AddSpotScreen />);
    expect(getByText('Finding your location…')).toBeTruthy();
    expect(queryByText('Sign in to add a new spot.')).toBeNull();
  });

  it('shows a permission-denied state with a working retry', async () => {
    setAuth({ id: 'user-1' });
    mockedRequestPermission.mockResolvedValue({ status: 'denied' });

    const { findByText } = render(<AddSpotScreen />);
    expect(await findByText('Location access is needed to find spots near you.')).toBeTruthy();

    mockedRequestPermission.mockResolvedValue({ status: 'granted' });
    fireEvent.press(await findByText('Try again'));
    expect(await findByText('Nothing found within range. Try again once you\'re closer.')).toBeTruthy();
  });

  it('shows an error state with retry when the search itself fails', async () => {
    setAuth({ id: 'user-1' });
    mockedSearchNearby.mockRejectedValueOnce(new Error('network'));

    const { findByText } = render(<AddSpotScreen />);
    expect(await findByText("Couldn't search nearby spots.")).toBeTruthy();

    mockedSearchNearby.mockResolvedValueOnce([makeCandidate({ name: 'Recovered Spot' })]);
    fireEvent.press(await findByText('Try again'));
    expect(await findByText('Recovered Spot')).toBeTruthy();
  });

  it('shows the empty-range message when nothing is found', async () => {
    setAuth({ id: 'user-1' });
    const { findByText } = render(<AddSpotScreen />);
    expect(await findByText("Nothing found within range. Try again once you're closer.")).toBeTruthy();
  });

  it('opens an already-in-CRAVE candidate directly instead of offering to confirm it', async () => {
    setAuth({ id: 'user-1' });
    mockedSearchNearby.mockResolvedValue([
      makeCandidate({ name: 'Existing Place', already_in_crave: true, place_id: 'place-123' }),
    ]);

    const { findByLabelText } = render(<AddSpotScreen />);
    fireEvent.press(await findByLabelText('Open Existing Place'));
    expect(mockPush).toHaveBeenCalledWith('/place/place-123');
    expect(mockedConfirmNewSpot).not.toHaveBeenCalled();
  });

  it('confirms a new spot, then shows it as Submitted and disabled', async () => {
    setAuth({ id: 'user-1' });
    mockedSearchNearby.mockResolvedValue([makeCandidate({ name: 'New Spot' })]);
    mockedConfirmNewSpot.mockResolvedValue({ status: 'pending', candidate_id: 'c1', confidence_score: 0.4 });

    const { findByLabelText, findByText } = render(<AddSpotScreen />);
    const confirmBtn = await findByLabelText('Confirm this is New Spot');
    await act(async () => {
      fireEvent.press(confirmBtn);
    });

    expect(mockedConfirmNewSpot).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'New Spot', external_id: 'ext-1' }),
    );
    expect(await findByText('Submitted')).toBeTruthy();
    expect(mockToastShow).toHaveBeenCalledWith(expect.stringContaining('added as a signal'));

    // Pressing it again while already confirmed must not resubmit.
    fireEvent.press(await findByLabelText('Confirm this is New Spot'));
    expect(mockedConfirmNewSpot).toHaveBeenCalledTimes(1);
  });

  it('toasts the server error message on a failed confirm, without marking it submitted', async () => {
    setAuth({ id: 'user-1' });
    mockedSearchNearby.mockResolvedValue([makeCandidate({ name: 'Flaky Spot' })]);
    mockedConfirmNewSpot.mockRejectedValue(new Error('Duplicate submission'));

    const { findByLabelText, findByText, queryByText } = render(<AddSpotScreen />);
    const confirmBtn = await findByLabelText('Confirm this is Flaky Spot');
    await act(async () => {
      fireEvent.press(confirmBtn);
    });

    expect(mockToastShow).toHaveBeenCalledWith('Duplicate submission');
    expect(queryByText('Submitted')).toBeNull();
    expect(await findByText("This is it")).toBeTruthy();
  });

  it('resets confirmed/confirming state on an account switch', async () => {
    setAuth({ id: 'user-A' });
    mockedSearchNearby.mockResolvedValue([makeCandidate({ external_id: 'shared', name: 'Some Spot' })]);
    mockedConfirmNewSpot.mockResolvedValue({ status: 'pending', candidate_id: 'c1', confidence_score: 0.4 });

    const { findByLabelText, findByText, rerender } = render(<AddSpotScreen />);
    const confirmBtn = await findByLabelText('Confirm this is Some Spot');
    await act(async () => {
      fireEvent.press(confirmBtn);
    });
    expect(await findByText('Submitted')).toBeTruthy();

    // Switch accounts -- the new account never submitted this candidate,
    // so it must not still show as "Submitted" for them.
    setAuth({ id: 'user-B' });
    rerender(<AddSpotScreen />);
    expect(await findByText('This is it')).toBeTruthy();
  });
});
