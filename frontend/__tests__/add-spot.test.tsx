import React from 'react';
import { Linking } from 'react-native';
import { act, fireEvent, render } from '@testing-library/react-native';
import * as Location from 'expo-location';
import AddSpotScreen from '../app/add-spot';
import { useAuthStore } from '../src/stores/authStore';
import { NearbyCandidate, confirmNewSpot, searchNearby } from '../src/api/nearby';
import type { PostingDraft } from '../src/stores/postingDraftStore';

const mockPush = jest.fn();
const mockReplace = jest.fn();
const mockBack = jest.fn();
let mockDraftId: string | undefined;
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace, back: mockBack }),
  useLocalSearchParams: () => ({ draftId: mockDraftId }),
}));
jest.mock('../src/stores/authStore', () => ({ useAuthStore: jest.fn() }));
jest.mock('../src/api/nearby', () => ({ searchNearby: jest.fn(), confirmNewSpot: jest.fn() }));

let mockDrafts: PostingDraft[] = [];
const mockSetDraftPlace = jest.fn();
const mockSetDraftCandidate = jest.fn();
jest.mock('../src/stores/postingDraftStore', () => ({
  usePostingDraftStore: (selector: (s: {
    drafts: PostingDraft[];
    setDraftPlace: (...args: unknown[]) => unknown;
    setDraftCandidate: (...args: unknown[]) => unknown;
  }) => unknown) =>
    selector({ drafts: mockDrafts, setDraftPlace: mockSetDraftPlace, setDraftCandidate: mockSetDraftCandidate }),
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

function makeDraft(overrides: Partial<PostingDraft> = {}): PostingDraft {
  const now = Date.now();
  return {
    id: 'draft-1',
    ownerId: 'user-1',
    localUri: 'file:///durable/draft-1.jpg',
    kind: 'photo',
    mimeType: 'image/jpeg',
    fileSize: 500000,
    uploadedMediaId: null,
    restaurantRef: { type: 'unresolved' },
    intent: 'social_post',
    reaction: null,
    caption: '',
    visibility: null,
    occurredAt: null,
    outcome: 'editing',
    lastError: null,
    createdAt: now,
    updatedAt: now,
    ...overrides,
  };
}

describe('AddSpotScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockDraftId = undefined;
    mockDrafts = [];
    mockedRequestPermission.mockResolvedValue({ status: 'granted', canAskAgain: true });
    mockedGetPosition.mockResolvedValue({ coords: { latitude: 37.7749, longitude: -122.4194 } });
    mockedSearchNearby.mockResolvedValue([]);
  });

  it('shows an unauthenticated prompt and opens AuthSheet without requesting location', async () => {
    setAuth(null);
    const { findByText, findByTestId } = render(<AddSpotScreen />);
    expect(await findByText('Sign in to add a missing restaurant.')).toBeTruthy();
    expect(mockedRequestPermission).not.toHaveBeenCalled();
    fireEvent.press(await findByText('Sign in'));
    expect(await findByTestId('auth-sheet-visible')).toBeTruthy();
  });

  it('stays locating while auth is hydrating', () => {
    setAuth(null, true);
    const { getByText, queryByText } = render(<AddSpotScreen />);
    expect(getByText('Finding nearby places…')).toBeTruthy();
    expect(queryByText('Sign in to add a missing restaurant.')).toBeNull();
  });

  it('shows a requestable permission-denied state with a working retry', async () => {
    setAuth({ id: 'user-1' });
    mockedRequestPermission.mockResolvedValue({ status: 'denied', canAskAgain: true });
    const { findByText } = render(<AddSpotScreen />);
    expect(await findByText('Location helps CRAVE find nearby missing places.')).toBeTruthy();
    mockedRequestPermission.mockResolvedValue({ status: 'granted', canAskAgain: true });
    fireEvent.press(await findByText('Try again'));
    expect(await findByText('Nothing nearby matched.')).toBeTruthy();
  });

  it('routes permanently blocked location permission to OS Settings instead of a dead retry loop', async () => {
    setAuth({ id: 'user-1' });
    mockedRequestPermission.mockResolvedValue({ status: 'denied', canAskAgain: false });
    const openSettings = jest.spyOn(Linking, 'openSettings').mockResolvedValue(undefined);
    const { findByText, queryByText } = render(<AddSpotScreen />);
    expect(await findByText('Enable location in Settings to find nearby missing places.')).toBeTruthy();
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
    expect(await findByText("Couldn't search nearby places.")).toBeTruthy();
    mockedSearchNearby.mockResolvedValueOnce([makeCandidate({ name: 'Recovered Spot' })]);
    fireEvent.press(await findByText('Try again'));
    expect(await findByText('Recovered Spot')).toBeTruthy();
  });

  it('shows the empty-range message when nothing is found', async () => {
    setAuth({ id: 'user-1' });
    const { findByText } = render(<AddSpotScreen />);
    expect(await findByText('Nothing nearby matched.')).toBeTruthy();
  });

  it('opens an already-in-CRAVE candidate directly when there is no draft', async () => {
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
    const confirmBtn = await findByLabelText('Submit New Spot for verification');
    await act(async () => { fireEvent.press(confirmBtn); });
    expect(mockedConfirmNewSpot).toHaveBeenCalledWith(expect.objectContaining({ name: 'New Spot', external_id: 'ext-1' }));
    expect(await findByText('Submitted')).toBeTruthy();
    expect(mockToastShow).toHaveBeenCalledWith(expect.stringContaining('added as a signal'));
    fireEvent.press(await findByLabelText('Submit New Spot for verification'));
    expect(mockedConfirmNewSpot).toHaveBeenCalledTimes(1);
  });

  it('toasts a failed confirm without marking the candidate submitted', async () => {
    setAuth({ id: 'user-1' });
    mockedSearchNearby.mockResolvedValue([makeCandidate({ name: 'Flaky Spot' })]);
    mockedConfirmNewSpot.mockRejectedValue(new Error('Duplicate submission'));
    const { findByLabelText, findByText, queryByText } = render(<AddSpotScreen />);
    const confirmBtn = await findByLabelText('Submit Flaky Spot for verification');
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
    const confirmBtn = await findByLabelText('Submit Some Spot for verification');
    await act(async () => { fireEvent.press(confirmBtn); });
    expect(await findByText('Submitted')).toBeTruthy();
    setAuth({ id: 'user-B' });
    rerender(<AddSpotScreen />);
    expect(await findByText('This is it')).toBeTruthy();
  });

  describe('posting draft carried over from food-evidence.tsx', () => {
    it('does not show a pending-draft banner when no draftId param is present', async () => {
      setAuth({ id: 'user-1' });
      mockedSearchNearby.mockResolvedValue([makeCandidate({ name: 'Plain Spot' })]);
      const { findByText, queryByText } = render(<AddSpotScreen />);
      expect(await findByText('Plain Spot')).toBeTruthy();
      expect(queryByText('Draft saved · no recapture required')).toBeNull();
    });

    it('selects an already-in-CRAVE place for a draft instead of opening it directly, then returns to the composer', async () => {
      mockDraftId = 'draft-1';
      mockDrafts = [makeDraft({ id: 'draft-1', kind: 'photo' })];
      setAuth({ id: 'user-1' });
      mockedSearchNearby.mockResolvedValue([makeCandidate({ name: 'Existing Place', already_in_crave: true, place_id: 'place-123' })]);

      const { findByText, findByLabelText } = render(<AddSpotScreen />);
      expect(await findByText('Draft saved · no recapture required')).toBeTruthy();

      fireEvent.press(await findByLabelText('Select Existing Place'));

      expect(mockSetDraftPlace).toHaveBeenCalledWith('draft-1', 'place-123', 'Existing Place');
      expect(mockToastShow).toHaveBeenCalledWith('Existing Place selected');
      expect(mockReplace).toHaveBeenCalledWith({ pathname: '/food-evidence', params: { draftId: 'draft-1' } });
      expect(mockPush).not.toHaveBeenCalledWith('/place/place-123');
    });

    it('shows the pending-draft banner for a video draft too', async () => {
      mockDraftId = 'draft-2';
      mockDrafts = [makeDraft({ id: 'draft-2', kind: 'video' })];
      setAuth({ id: 'user-1' });
      mockedSearchNearby.mockResolvedValue([makeCandidate({ name: 'Existing Place', already_in_crave: true, place_id: 'place-123' })]);

      const { findByText, findByLabelText } = render(<AddSpotScreen />);
      expect(await findByText('Draft saved · no recapture required')).toBeTruthy();

      fireEvent.press(await findByLabelText('Select Existing Place'));

      expect(mockSetDraftPlace).toHaveBeenCalledWith('draft-2', 'place-123', 'Existing Place');
    });

    it('still shows the pending-draft banner while a previous commit is in flight', async () => {
      // The exclusivity guard itself lives in the store (see
      // postingDraftStore.test.ts), not this component -- this only checks
      // the component's own display logic, which renders the banner off of
      // draft presence, not draft.outcome.
      mockDraftId = 'draft-1';
      mockDrafts = [makeDraft({ id: 'draft-1', outcome: 'committing' })];
      setAuth({ id: 'user-1' });
      mockedSearchNearby.mockResolvedValue([makeCandidate({ name: 'Existing Place', already_in_crave: true, place_id: 'place-123' })]);

      const { findByText } = render(<AddSpotScreen />);
      await findByText('Existing Place');
      expect(await findByText('Draft saved · no recapture required')).toBeTruthy();
    });

    it('does not silently drop a draft when confirming a brand-new candidate -- records the candidate reference and returns to the composer', async () => {
      // confirmNewSpot() only ever returns a candidate_id (a DiscoveryCandidate,
      // not a Place), so there is no place_id yet to attach the draft to on
      // this branch -- this must not pretend it uploaded, and must not lose
      // the reference either (setDraftCandidate persists it for the
      // foreground resolver in _layout.tsx to pick up later).
      mockDraftId = 'draft-1';
      mockDrafts = [makeDraft({ id: 'draft-1', kind: 'photo' })];
      setAuth({ id: 'user-1' });
      mockedSearchNearby.mockResolvedValue([makeCandidate({ name: 'New Spot' })]);
      mockedConfirmNewSpot.mockResolvedValue({ status: 'pending', candidate_id: 'cand-9', confidence_score: 0.4 });

      const { findByLabelText } = render(<AddSpotScreen />);
      const confirmBtn = await findByLabelText('Submit New Spot for verification');
      await act(async () => { fireEvent.press(confirmBtn); });

      expect(mockSetDraftPlace).not.toHaveBeenCalled();
      expect(mockSetDraftCandidate).toHaveBeenCalledWith('draft-1', 'cand-9', 'New Spot');
      expect(mockToastShow).toHaveBeenCalledWith("Restaurant submitted. Your draft is safe while we're verifying it.");
      expect(mockReplace).toHaveBeenCalledWith({ pathname: '/food-evidence', params: { draftId: 'draft-1' } });
    });

    it('shows the plain confirm toast (no draft-specific copy) when there is no pending draft', async () => {
      setAuth({ id: 'user-1' });
      mockedSearchNearby.mockResolvedValue([makeCandidate({ name: 'New Spot' })]);
      mockedConfirmNewSpot.mockResolvedValue({ status: 'pending', candidate_id: 'cand-9', confidence_score: 0.4 });

      const { findByLabelText } = render(<AddSpotScreen />);
      const confirmBtn = await findByLabelText('Submit New Spot for verification');
      await act(async () => { fireEvent.press(confirmBtn); });

      expect(mockSetDraftCandidate).not.toHaveBeenCalled();
      expect(mockToastShow).toHaveBeenCalledWith("Got it — added as a signal. It'll appear once confirmed by more activity.");
    });
  });
});
