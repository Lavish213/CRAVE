// app/food-evidence.tsx -- Posting V2-A rewrite. Locks in: the sign-in gate
// (new -- a durable draft needs an owner the moment it's created), that
// capture immediately persists a durable PostingDraft (not just local
// component state) via createDraftFromCapture, and that "Continue" carries
// only a draftId, not raw media data, to add-spot.tsx.
import React from 'react';
import { act, fireEvent, render } from '@testing-library/react-native';
import { Alert } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import FoodEvidenceScreen from '../app/food-evidence';
import { useAuthStore } from '../src/stores/authStore';
import { usePostingDraftStore } from '../src/stores/postingDraftStore';

const mockPush = jest.fn();
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush }),
}));
jest.mock('expo-image-picker', () => ({
  requestCameraPermissionsAsync: jest.fn(),
  launchCameraAsync: jest.fn(),
  launchImageLibraryAsync: jest.fn(),
}));
jest.mock('../src/stores/authStore', () => ({ useAuthStore: jest.fn() }));
const mockCreateDraftFromCapture = jest.fn();
jest.mock('../src/stores/postingDraftStore', () => ({
  usePostingDraftStore: (selector: (s: { createDraftFromCapture: (...args: unknown[]) => unknown }) => unknown) =>
    selector({ createDraftFromCapture: mockCreateDraftFromCapture }),
}));
const mockToastShow = jest.fn();
jest.mock('../src/hooks/useToast', () => ({
  useToast: (selector: (s: { show: (msg: string) => void }) => unknown) => selector({ show: mockToastShow }),
}));
jest.mock('../src/components/AuthSheet', () => {
  const { Text } = require('react-native');
  return { AuthSheet: ({ visible }: { visible: boolean }) => (visible ? <Text testID="auth-sheet-visible">auth</Text> : null) };
});

const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;
const mockedRequestCameraPermission = ImagePicker.requestCameraPermissionsAsync as jest.Mock;
const mockedLaunchCamera = ImagePicker.launchCameraAsync as jest.Mock;
const mockedLaunchLibrary = ImagePicker.launchImageLibraryAsync as jest.Mock;

function setAuth(user: { id: string } | null) {
  mockedUseAuthStore.mockImplementation((selector: (s: unknown) => unknown) => selector({ user }));
}

describe('FoodEvidenceScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setAuth({ id: 'user-1' });
  });

  it('shows a sign-in gate and never touches the camera/picker when signed out', async () => {
    setAuth(null);
    const { findByText, findByTestId, queryByLabelText } = render(<FoodEvidenceScreen />);
    expect(await findByText('Sign in to record food evidence')).toBeTruthy();
    expect(queryByLabelText('Take Photo')).toBeNull();

    fireEvent.press(await findByText('Sign in'));
    expect(await findByTestId('auth-sheet-visible')).toBeTruthy();
    expect(mockedRequestCameraPermission).not.toHaveBeenCalled();
  });

  it('does not show the Continue button until media is captured', () => {
    const { queryByLabelText } = render(<FoodEvidenceScreen />);
    expect(queryByLabelText('Identify restaurant')).toBeNull();
  });

  it('persists a camera photo as a durable draft (not just local state) and carries only draftId to add-spot', async () => {
    mockedRequestCameraPermission.mockResolvedValue({ granted: true });
    mockedLaunchCamera.mockResolvedValue({
      canceled: false,
      assets: [{ uri: 'file://photo.jpg', fileSize: 500000, mimeType: 'image/jpeg' }],
    });
    mockCreateDraftFromCapture.mockResolvedValue({ id: 'draft-1', localUri: 'file:///durable/draft-1.jpg' });

    const { findByLabelText, findByText } = render(<FoodEvidenceScreen />);
    await act(async () => {
      fireEvent.press(await findByLabelText('Take Photo'));
    });

    expect(mockCreateDraftFromCapture).toHaveBeenCalledWith({
      ownerId: 'user-1',
      sourceUri: 'file://photo.jpg',
      kind: 'photo',
      mimeType: 'image/jpeg',
      fileSize: 500000,
    });
    expect(await findByText('Photo saved')).toBeTruthy();

    fireEvent.press(await findByLabelText('Identify restaurant'));
    expect(mockPush).toHaveBeenCalledWith({ pathname: '/add-spot', params: { draftId: 'draft-1' } });
  });

  it('persists a library-picked video as a durable draft', async () => {
    mockedLaunchLibrary.mockResolvedValue({
      canceled: false,
      assets: [{ uri: 'file://clip.mov' }],
    });
    mockCreateDraftFromCapture.mockResolvedValue({ id: 'draft-2', localUri: 'file:///durable/draft-2.mov' });

    const { findByLabelText, findByText } = render(<FoodEvidenceScreen />);
    await act(async () => {
      fireEvent.press(await findByLabelText('Choose Video'));
    });

    expect(mockCreateDraftFromCapture).toHaveBeenCalledWith({
      ownerId: 'user-1',
      sourceUri: 'file://clip.mov',
      kind: 'video',
      mimeType: undefined,
      fileSize: undefined,
    });
    expect(await findByText('Video saved')).toBeTruthy();

    fireEvent.press(await findByLabelText('Identify restaurant'));
    expect(mockPush).toHaveBeenCalledWith({ pathname: '/add-spot', params: { draftId: 'draft-2' } });
  });

  it('toasts instead of crashing when creating the durable draft fails', async () => {
    mockedLaunchLibrary.mockResolvedValue({
      canceled: false,
      assets: [{ uri: 'file://photo.jpg', fileSize: 100, mimeType: 'image/jpeg' }],
    });
    mockCreateDraftFromCapture.mockRejectedValue(new Error("Couldn't save that capture"));

    const { findByLabelText, queryByLabelText } = render(<FoodEvidenceScreen />);
    await act(async () => {
      fireEvent.press(await findByLabelText('Choose Photo'));
    });

    expect(mockToastShow).toHaveBeenCalledWith("Couldn't save that capture");
    expect(queryByLabelText('Identify restaurant')).toBeNull();
  });

  it('warns instead of opening the camera when camera permission is denied', async () => {
    mockedRequestCameraPermission.mockResolvedValue({ granted: false });
    const alertSpy = jest.spyOn(Alert, 'alert').mockImplementation(() => {});

    const { findByLabelText } = render(<FoodEvidenceScreen />);
    await act(async () => {
      fireEvent.press(await findByLabelText('Take Photo'));
    });

    expect(mockedLaunchCamera).not.toHaveBeenCalled();
    expect(mockCreateDraftFromCapture).not.toHaveBeenCalled();
    expect(alertSpy).toHaveBeenCalledWith('Camera unavailable', expect.any(String));
    alertSpy.mockRestore();
  });

  it('does nothing when the picker is cancelled', async () => {
    mockedLaunchLibrary.mockResolvedValue({ canceled: true, assets: null });

    const { findByLabelText, queryByLabelText, queryByText } = render(<FoodEvidenceScreen />);
    fireEvent.press(await findByLabelText('Choose Photo'));

    expect(queryByText('Photo saved')).toBeNull();
    expect(queryByLabelText('Identify restaurant')).toBeNull();
    expect(mockCreateDraftFromCapture).not.toHaveBeenCalled();
  });
});
