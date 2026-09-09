import React from 'react';
import { Linking } from 'react-native';
import { act, fireEvent, render } from '@testing-library/react-native';
import * as Location from 'expo-location';
import AddSpotScreen from '../app/add-spot';
import { useAuthStore } from '../src/stores/authStore';
import { NearbyCandidate, confirmNewSpot, searchNearby } from '../src/api/nearby';

const mockPush = jest.fn();
let mockParams: Record<string, string | undefined> = {};
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useLocalSearchParams: () => mockParams,
}));
jest.mock('../src/stores/authStore', () => ({ useAuthStore: jest.fn() }));
jest.mock('../src/api/nearby', () => ({ searchNearby: jest.fn(), confirmNewSpot: jest.fn() }));
const mockUpload = jest.fn();
jest.mock('../src/hooks/useUploadImage', () => ({
  useUploadImage: () => ({ upload: mockUpload }),
}));
const mockRecordVideo = jest.fn();
jest.mock('../src/stores/videoQueueStore', () => ({
  useVideoQueueStore: (selector: (s: { recordVideo: (...args: unknown[]) => unknown }) => unknown) =>
    selector({ recordVideo: mockRecordVideo }),
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
  useToast: (selector: (s: { show: (msg: string) => void }) => unknown) => selector({ show: mockToastShow }),
}));
jest.mock('../src/components/AuthSheet', () => {
  const { Text } = require('react-native');
  return { AuthSheet: ({ visible }: { visible: boolean }) => visible ? <Text testID="auth-sheet-visible">auth</Text> : null };
});

const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;
const mockedSearchNearby = searchNearby as jest.MockedFunction<typeof searchNearby>;
const mockedConfirmNewSpot = confirmNewSpot as jest.MockedFunction<typeof confirmNewSpot>;
const mockedRequestPermission = Location.requestForegroundPermissionsAsync as jest.Mock;
const mockedGetPosition = Location.getCurrentPositionAsync as jest.Mock;

function setAuth(user: { id: string } | null, loading = false) {
  mockedUseAuthStore.mockImplementation((selector: (s: unknown) => unknown) => selector({ user, loading }));
}

function makeCandidate(overrides: Partial<NearbyCandidate> = {}): NearbyCandidate {
  return {
    external_id: 'ext-1', name: 'Tasty Spot', address: '123 Main St', lat: 37.7, lng: -122.4,
    category_hint: 'Cafe', distance_m: 42, already_in_crave: false, place_id: null, ...overrides,
  };
}

describe('AddSpotScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockParams = {};
    mockedRequestPermission.mockResolvedValue({ status: 'granted', canAskAgain: true });
    mockedGetPosition.mockResolvedValue({ coords: { latitude: 37.7749, longitude: -122.4194 } });
    mockedSearchNearby.mockResolvedValue([]);
  });

  it('shows an unauthenticated prompt and opens AuthSheet without requesting location', async () => {
    setAuth(null);
    const { findByText, findByTestId } = render(<AddSpotScreen />);
    expect(await findByText('Sign in to add a new spot.')).toBeTruthy();
    expect(mockedRequestPermission).not.toHaveBeenCalled();
    fireEvent.press(await findByText('Sign in'));
    expect(await findByTestId('auth-sheet-visible')).toBeTruthy();
  });

  it('stays locating while auth is hydrating', () => {
    setAuth(null, true);
    const { getByText, queryByText } = render(<AddSpotScreen />);
    expect(getByText('Finding your location…')).toBeTruthy();
    expect(queryByText('Sign in to add a new spot.')).toBeNull();
  });

  it('shows a requestable permission-denied state with a working retry', async () => {
    setAuth({ id: 'user-1' });
    mockedRequestPermission.mockResolvedValue({ status: 'denied', canAskAgain: true });
    const { findByText } = render(<AddSpotScreen />);
    expect(await findByText('Location access is needed to find spots near you.')).toBeTruthy();
    mockedRequestPermission.mockResolvedValue({ status: 'granted', canAskAgain: true });
    fireEvent.press(await findByText('Try again'));
    expect(await findByText("Nothing found within range. Try again once you're closer.")).toBeTruthy();
  });

  it('routes permanently blocked location permission to OS Settings instead of a dead retry loop', async () => {
    setAuth({ id: 'user-1' });
    mockedRequestPermission.mockResolvedValue({ status: 'denied', canAskAgain: false });
    const openSettings = jest.spyOn(Linking, 'openSettings').mockResolvedValue(undefined);
    const { findByText, queryByText } = render(<AddSpotScreen />);
    expect(await findByText(/Location access is turned off for CRAVE/)).toBeTruthy();
    expect(queryByText('Try again')).toBeNull();
    fireEvent.press(await findByText('Open Settings'));
    expect(openSettings).toHaveBeenCalledTimes(1);
    expect(mockedRequestPermission).toHaveBeenCalledTimes(1);
    openSettings.mockRestore();
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

  it('opens an already-in-CRAVE candidate directly', async () => {
    setAuth({ id: 'user-1' });
    mockedSearchNearby.mockResolvedValue([makeCandidate({ name: 'Existing Place', already_in_crave: true, place_id: 'place-123' })]);
    const { findByLabelText } = render(<AddSpotScreen />);
    fireEvent.press(await findByLabelText('Open Existing Place'));
    expect(mockPush).toHaveBeenCalledWith('/place/place-123');
    expect(mockedConfirmNewSpot).not.toHaveBeenCalled();
  });

  it('confirms a new spot then shows it as Submitted and disabled', async () => {
    setAuth({ id: 'user-1' });
    mockedSearchNearby.mockResolvedValue([makeCandidate({ name: 'New Spot' })]);
    mockedConfirmNewSpot.mockResolvedValue({ status: 'pending', candidate_id: 'c1', confidence_score: 0.4 });
    const { findByLabelText, findByText } = render(<AddSpotScreen />);
    const confirmBtn = await findByLabelText('Confirm this is New Spot');
    await act(async () => { fireEvent.press(confirmBtn); });
    expect(mockedConfirmNewSpot).toHaveBeenCalledWith(expect.objectContaining({ name: 'New Spot', external_id: 'ext-1' }));
    expect(await findByText('Submitted')).toBeTruthy();
    expect(mockToastShow).toHaveBeenCalledWith(expect.stringContaining('added as a signal'));
    fireEvent.press(await findByLabelText('Confirm this is New Spot'));
    expect(mockedConfirmNewSpot).toHaveBeenCalledTimes(1);
  });

  it('toasts a failed confirm without marking the candidate submitted', async () => {
    setAuth({ id: 'user-1' });
    mockedSearchNearby.mockResolvedValue([makeCandidate({ name: 'Flaky Spot' })]);
    mockedConfirmNewSpot.mockRejectedValue(new Error('Duplicate submission'));
    const { findByLabelText, findByText, queryByText } = render(<AddSpotScreen />);
    const confirmBtn = await findByLabelText('Confirm this is Flaky Spot');
    await act(async () => { fireEvent.press(confirmBtn); });
    expect(mockToastShow).toHaveBeenCalledWith('Duplicate submission');
    expect(queryByText('Submitted')).toBeNull();
    expect(await findByText('This is it')).toBeTruthy();
  });

  it('resets confirmed/confirming state on an account switch', async () => {
    setAuth({ id: 'user-A' });
    mockedSearchNearby.mockResolvedValue([makeCandidate({ external_id: 'shared', name: 'Some Spot' })]);
    mockedConfirmNewSpot.mockResolvedValue({ status: 'pending', candidate_id: 'c1', confidence_score: 0.4 });
    const { findByLabelText, findByText, rerender } = render(<AddSpotScreen />);
    const confirmBtn = await findByLabelText('Confirm this is Some Spot');
    await act(async () => { fireEvent.press(confirmBtn); });
    expect(await findByText('Submitted')).toBeTruthy();
    setAuth({ id: 'user-B' });
    rerender(<AddSpotScreen />);
    expect(await findByText('This is it')).toBeTruthy();
  });

  describe('media carried over from food-evidence.tsx', () => {
    it('does not show a pending-media banner when no media params are present', async () => {
      setAuth({ id: 'user-1' });
      mockedSearchNearby.mockResolvedValue([makeCandidate({ name: 'Plain Spot' })]);
      const { findByText, queryByText } = render(<AddSpotScreen />);
      expect(await findByText('Plain Spot')).toBeTruthy();
      expect(queryByText(/ready — tap a place below/)).toBeNull();
    });

    it('uploads a pending photo when opening an already-in-CRAVE place, instead of dropping it', async () => {
      mockParams = { mediaUri: 'file://photo.jpg', mediaKind: 'photo', mediaFileSize: '1000000', mediaMimeType: 'image/jpeg' };
      setAuth({ id: 'user-1' });
      mockedSearchNearby.mockResolvedValue([makeCandidate({ name: 'Existing Place', already_in_crave: true, place_id: 'place-123' })]);
      mockUpload.mockResolvedValue('image-1');

      const { findByText, findByLabelText } = render(<AddSpotScreen />);
      expect(await findByText('Photo ready — tap a place below to attach it.')).toBeTruthy();

      fireEvent.press(await findByLabelText('Open Existing Place'));
      expect(mockPush).toHaveBeenCalledWith('/place/place-123');
      await act(async () => {});

      expect(mockUpload).toHaveBeenCalledWith(
        { uri: 'file://photo.jpg', fileSize: 1000000, mimeType: 'image/jpeg' },
        'place-123',
        'food',
      );
      expect(mockToastShow).toHaveBeenCalledWith('Photo submitted for this place');
    });

    it('queues a pending video via the video store when opening an already-in-CRAVE place', async () => {
      mockParams = { mediaUri: 'file://clip.mov', mediaKind: 'video' };
      setAuth({ id: 'user-1' });
      mockedSearchNearby.mockResolvedValue([makeCandidate({ name: 'Existing Place', already_in_crave: true, place_id: 'place-123' })]);
      mockRecordVideo.mockResolvedValue({ id: 'local-1' });

      const { findByLabelText } = render(<AddSpotScreen />);
      fireEvent.press(await findByLabelText('Open Existing Place'));
      await act(async () => {});

      expect(mockRecordVideo).toHaveBeenCalledWith({
        sourceUri: 'file://clip.mov',
        placeId: 'place-123',
        contentType: 'video/quicktime',
        uploadedBy: 'user-1',
        templateId: null,
      });
      expect(mockToastShow).toHaveBeenCalledWith("Saved — it'll post as soon as you're online.");
    });

    it('does not silently drop pending media when confirming a brand-new candidate -- says so explicitly instead', async () => {
      // confirmNewSpot() only ever returns a candidate_id (a DiscoveryCandidate,
      // not a Place), so there is no place_id yet to attach media to on this
      // branch -- this must not pretend it uploaded.
      mockParams = { mediaUri: 'file://photo.jpg', mediaKind: 'photo', mediaFileSize: '1000000', mediaMimeType: 'image/jpeg' };
      setAuth({ id: 'user-1' });
      mockedSearchNearby.mockResolvedValue([makeCandidate({ name: 'New Spot' })]);
      mockedConfirmNewSpot.mockResolvedValue({ status: 'pending', candidate_id: 'c1', confidence_score: 0.4 });

      const { findByLabelText } = render(<AddSpotScreen />);
      const confirmBtn = await findByLabelText('Confirm this is New Spot');
      await act(async () => { fireEvent.press(confirmBtn); });

      expect(mockUpload).not.toHaveBeenCalled();
      expect(mockToastShow).toHaveBeenCalledWith(
        expect.stringContaining("Come back once it's live to add your photo."),
      );
    });

    it('does not attach the same media a second time to a different candidate', async () => {
      mockParams = { mediaUri: 'file://photo.jpg', mediaKind: 'photo', mediaFileSize: '1000000', mediaMimeType: 'image/jpeg' };
      setAuth({ id: 'user-1' });
      mockedSearchNearby.mockResolvedValue([
        makeCandidate({ external_id: 'a', name: 'First Place', already_in_crave: true, place_id: 'place-a' }),
        makeCandidate({ external_id: 'b', name: 'Second Place', already_in_crave: true, place_id: 'place-b' }),
      ]);
      mockUpload.mockResolvedValue('image-1');

      const { findByLabelText } = render(<AddSpotScreen />);
      fireEvent.press(await findByLabelText('Open First Place'));
      await act(async () => {});
      fireEvent.press(await findByLabelText('Open Second Place'));
      await act(async () => {});

      expect(mockUpload).toHaveBeenCalledTimes(1);
      expect(mockUpload).toHaveBeenCalledWith(expect.anything(), 'place-a', 'food');
    });

    it('toasts a failure instead of crashing when the upload itself fails', async () => {
      mockParams = { mediaUri: 'file://photo.jpg', mediaKind: 'photo', mediaFileSize: '1000000', mediaMimeType: 'image/jpeg' };
      setAuth({ id: 'user-1' });
      mockedSearchNearby.mockResolvedValue([makeCandidate({ name: 'Existing Place', already_in_crave: true, place_id: 'place-123' })]);
      mockUpload.mockRejectedValue(new Error('Upload to storage failed'));

      const { findByLabelText } = render(<AddSpotScreen />);
      fireEvent.press(await findByLabelText('Open Existing Place'));
      await act(async () => {});

      expect(mockToastShow).toHaveBeenCalledWith('Upload to storage failed');
    });
  });
});
