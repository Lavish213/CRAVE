// app/food-evidence.tsx -- first dedicated coverage. Locks in the fix for a
// confirmed bug found in a full app-wide screen audit: "Continue" used to
// navigate to /add-spot with no params at all, silently discarding the
// photo/video just captured (add-spot.tsx had no way of knowing any media
// was ever selected). Now the captured {uri, kind, fileSize, mimeType} is
// carried through as route params instead.
import React from 'react';
import { act, fireEvent, render } from '@testing-library/react-native';
import { Alert } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import FoodEvidenceScreen from '../app/food-evidence';

const mockPush = jest.fn();
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush }),
}));
jest.mock('expo-image-picker', () => ({
  requestCameraPermissionsAsync: jest.fn(),
  launchCameraAsync: jest.fn(),
  launchImageLibraryAsync: jest.fn(),
}));

const mockedRequestCameraPermission = ImagePicker.requestCameraPermissionsAsync as jest.Mock;
const mockedLaunchCamera = ImagePicker.launchCameraAsync as jest.Mock;
const mockedLaunchLibrary = ImagePicker.launchImageLibraryAsync as jest.Mock;

describe('FoodEvidenceScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('does not show the Continue button until media is selected', () => {
    const { queryByLabelText } = render(<FoodEvidenceScreen />);
    expect(queryByLabelText('Identify restaurant')).toBeNull();
  });

  it('carries a camera photo (uri, kind, fileSize, mimeType) through to add-spot instead of dropping it', async () => {
    mockedRequestCameraPermission.mockResolvedValue({ granted: true });
    mockedLaunchCamera.mockResolvedValue({
      canceled: false,
      assets: [{ uri: 'file://photo.jpg', fileSize: 500000, mimeType: 'image/jpeg' }],
    });

    const { findByLabelText, findByText } = render(<FoodEvidenceScreen />);
    fireEvent.press(await findByLabelText('Take Photo'));
    expect(await findByText('Photo selected')).toBeTruthy();

    fireEvent.press(await findByLabelText('Identify restaurant'));
    expect(mockPush).toHaveBeenCalledWith({
      pathname: '/add-spot',
      params: {
        mediaUri: 'file://photo.jpg',
        mediaKind: 'photo',
        mediaFileSize: '500000',
        mediaMimeType: 'image/jpeg',
      },
    });
  });

  it('carries a library-picked video through, with empty fileSize/mimeType strings when the picker does not report them', async () => {
    mockedLaunchLibrary.mockResolvedValue({
      canceled: false,
      assets: [{ uri: 'file://clip.mov' }],
    });

    const { findByLabelText, findByText } = render(<FoodEvidenceScreen />);
    fireEvent.press(await findByLabelText('Choose Video'));
    expect(await findByText('Video selected')).toBeTruthy();

    fireEvent.press(await findByLabelText('Identify restaurant'));
    expect(mockPush).toHaveBeenCalledWith({
      pathname: '/add-spot',
      params: {
        mediaUri: 'file://clip.mov',
        mediaKind: 'video',
        mediaFileSize: '',
        mediaMimeType: '',
      },
    });
  });

  it('warns instead of opening the camera when camera permission is denied', async () => {
    mockedRequestCameraPermission.mockResolvedValue({ granted: false });
    const alertSpy = jest.spyOn(Alert, 'alert').mockImplementation(() => {});

    const { findByLabelText } = render(<FoodEvidenceScreen />);
    await act(async () => {
      fireEvent.press(await findByLabelText('Take Photo'));
    });

    expect(mockedLaunchCamera).not.toHaveBeenCalled();
    expect(alertSpy).toHaveBeenCalledWith('Camera unavailable', expect.any(String));
    alertSpy.mockRestore();
  });

  it('does nothing when the picker is cancelled', async () => {
    mockedLaunchLibrary.mockResolvedValue({ canceled: true, assets: null });

    const { findByLabelText, queryByLabelText, queryByText } = render(<FoodEvidenceScreen />);
    fireEvent.press(await findByLabelText('Choose Photo'));

    expect(queryByText('Photo selected')).toBeNull();
    expect(queryByLabelText('Identify restaurant')).toBeNull();
  });
});
