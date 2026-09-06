// record-video/[placeId].tsx — first dedicated coverage. Locks in: the
// permission-unknown/denied/granted gating, the record/stop control
// wiring to the camera ref's imperative recordAsync/stopRecording, the
// cancelled-recording no-op (no uri returned), the successful
// save-and-navigate-back path (with the right contentType inferred from
// the recorded file extension), a failed save's toast without
// navigating away, and the close button.
//
// While writing this, found the record and close buttons had no
// accessibilityLabel at all -- fixed in the same commit (small, safe,
// and a real accessibility gap independent of testability).
import React from 'react';
import { act, fireEvent, render } from '@testing-library/react-native';
import RecordVideoScreen from '../app/record-video/[placeId]';
import { useCameraPermissions, useMicrophonePermissions } from 'expo-camera';
import { useAuthStore } from '../src/stores/authStore';
import { useVideoQueueStore } from '../src/stores/videoQueueStore';

const mockBack = jest.fn();
jest.mock('expo-router', () => ({
  useRouter: () => ({ back: mockBack }),
  useLocalSearchParams: () => ({ placeId: 'place-1' }),
}));

const mockRecordAsync = jest.fn();
const mockStopRecording = jest.fn();
// CameraView is a forwardRef component whose ref exposes the imperative
// recordAsync/stopRecording methods the screen calls directly -- a real
// native view can't render under RTL/jsdom, so this stub renders a
// harmless placeholder and wires the ref to the same two jest.fn()s
// every test controls.
jest.mock('expo-camera', () => {
  const React = require('react');
  const { View } = require('react-native');
  return {
    CameraView: React.forwardRef((props: any, ref: any) => {
      React.useImperativeHandle(ref, () => ({
        recordAsync: mockRecordAsync,
        stopRecording: mockStopRecording,
      }));
      return <View testID="camera-view" />;
    }),
    useCameraPermissions: jest.fn(),
    useMicrophonePermissions: jest.fn(),
  };
});
jest.mock('react-native-safe-area-context', () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock('../src/hooks/useVideoTemplates', () => ({
  useVideoTemplates: () => ({ templates: [], loading: false }),
}));
jest.mock('../src/stores/authStore', () => ({
  useAuthStore: jest.fn(),
}));
jest.mock('../src/stores/videoQueueStore', () => ({
  useVideoQueueStore: jest.fn(),
}));
const mockToastShow = jest.fn();
jest.mock('../src/hooks/useToast', () => ({
  useToast: (selector: (s: { show: (msg: string) => void }) => unknown) =>
    selector({ show: mockToastShow }),
}));
jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  ImpactFeedbackStyle: { Medium: 'medium' },
}));

const mockedUseCameraPermissions = useCameraPermissions as jest.Mock;
const mockedUseMicrophonePermissions = useMicrophonePermissions as jest.Mock;
const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;
const mockedUseVideoQueueStore = useVideoQueueStore as unknown as jest.Mock;
const mockRequestCameraPermission = jest.fn().mockResolvedValue({ granted: true });
const mockRequestMicPermission = jest.fn().mockResolvedValue({ granted: true });
const mockRecordVideo = jest.fn().mockResolvedValue(undefined);
const mockRunSyncPass = jest.fn().mockResolvedValue(undefined);

function setPermissions(granted: boolean | null, canAskAgain = true) {
  const state = granted === null ? null : { granted, canAskAgain };
  mockedUseCameraPermissions.mockReturnValue([state, mockRequestCameraPermission]);
  mockedUseMicrophonePermissions.mockReturnValue([state, mockRequestMicPermission]);
}

// Keeps the hook-style selector and useAuthStore.getState() (which the
// screen now reads directly, to check the *current* auth state rather
// than a closure-captured one -- see the stale-closure regression test
// below) reporting the same user, the way the real store would.
function setAuthUser(user: { id: string } | null) {
  mockedUseAuthStore.mockImplementation((selector: (s: unknown) => unknown) => selector({ user }));
  (mockedUseAuthStore as any).getState = jest.fn(() => ({ user }));
}

describe('RecordVideoScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setPermissions(true);
    setAuthUser({ id: 'user-1' });
    mockedUseVideoQueueStore.mockImplementation((selector: (s: unknown) => unknown) =>
      selector({ recordVideo: mockRecordVideo, runSyncPass: mockRunSyncPass }),
    );
    mockRecordVideo.mockResolvedValue(undefined);
    mockRunSyncPass.mockResolvedValue(undefined);
  });

  it('shows a sign-in prompt instead of the camera when signed out, and never records', () => {
    setAuthUser(null);
    const { getByText, queryByTestId } = render(<RecordVideoScreen />);

    expect(getByText('Sign in to record a food video.')).toBeTruthy();
    expect(queryByTestId('camera-view')).toBeNull();
  });

  it('shows a Settings-recovery prompt instead of an inert "Allow Access" when permission is permanently blocked', async () => {
    // canAskAgain: false means the OS won't re-prompt -- "Allow Access"
    // would silently no-op if shown here.
    setPermissions(false, false);
    const { getByText, queryByText } = render(<RecordVideoScreen />);

    expect(
      getByText('Camera and microphone access is blocked. Enable it in Settings to record a food video.'),
    ).toBeTruthy();
    expect(queryByText('Allow Access')).toBeNull();

    const { Linking } = require('react-native');
    jest.spyOn(Linking, 'openSettings').mockResolvedValue(undefined);
    await act(async () => {
      fireEvent.press(getByText('Open Settings'));
    });
    expect(Linking.openSettings).toHaveBeenCalled();
    expect(mockRequestCameraPermission).not.toHaveBeenCalled();
  });

  it('renders nothing but an empty container while permissions are still resolving', () => {
    setPermissions(null);
    const { queryByTestId } = render(<RecordVideoScreen />);
    expect(queryByTestId('camera-view')).toBeNull();
  });

  it('shows a permission prompt when denied, and requests both camera and mic on tap', async () => {
    setPermissions(false);
    const { getByText } = render(<RecordVideoScreen />);

    expect(getByText('CRAVE needs camera and microphone access to record a food video.')).toBeTruthy();
    await act(async () => {
      fireEvent.press(getByText('Allow Access'));
    });
    expect(mockRequestCameraPermission).toHaveBeenCalled();
    expect(mockRequestMicPermission).toHaveBeenCalled();
  });

  it('renders the camera and record button once both permissions are granted', () => {
    const { getByTestId, getByLabelText } = render(<RecordVideoScreen />);
    expect(getByTestId('camera-view')).toBeTruthy();
    expect(getByLabelText('Start recording')).toBeTruthy();
  });

  it('starts recording via the camera ref on tap', async () => {
    mockRecordAsync.mockImplementation(() => new Promise(() => {})); // never resolves in this test
    const { getByLabelText } = render(<RecordVideoScreen />);

    await act(async () => {
      fireEvent.press(getByLabelText('Start recording'));
    });
    expect(mockRecordAsync).toHaveBeenCalledWith({ maxDuration: 10 });
  });

  it('does nothing when the recording is cancelled with no output uri', async () => {
    mockRecordAsync.mockResolvedValue({ uri: undefined });
    const { getByLabelText } = render(<RecordVideoScreen />);

    await act(async () => {
      fireEvent.press(getByLabelText('Start recording'));
    });

    expect(mockRecordVideo).not.toHaveBeenCalled();
    expect(mockBack).not.toHaveBeenCalled();
  });

  it('toasts an error when recordAsync itself throws, instead of silently resetting', async () => {
    // Confirmed release defect (docs/SCREEN_UX_FINDINGS_TRIAGE.md): this
    // was the one failure path in this file with no user-facing toast --
    // a real recording failure produced zero feedback.
    mockRecordAsync.mockRejectedValue(new Error('camera hardware error'));
    const { getByLabelText } = render(<RecordVideoScreen />);

    await act(async () => {
      fireEvent.press(getByLabelText('Start recording'));
    });

    expect(mockToastShow).toHaveBeenCalledWith("Couldn't record that video. Try again.");
    expect(mockRecordVideo).not.toHaveBeenCalled();
  });

  it('saves the recording with the right contentType, syncs, toasts, and navigates back', async () => {
    mockRecordAsync.mockResolvedValue({ uri: 'file:///tmp/clip.mov' });
    const { getByLabelText } = render(<RecordVideoScreen />);

    await act(async () => {
      fireEvent.press(getByLabelText('Start recording'));
    });

    expect(mockRecordVideo).toHaveBeenCalledWith({
      sourceUri: 'file:///tmp/clip.mov',
      placeId: 'place-1',
      contentType: 'video/quicktime',
      uploadedBy: 'user-1',
      templateId: null,
    });
    expect(mockRunSyncPass).toHaveBeenCalledWith('user-1');
    expect(mockToastShow).toHaveBeenCalledWith("Saved — it'll post as soon as you're online.");
    expect(mockBack).toHaveBeenCalled();
  });

  it('does not queue the recording if the user signed out while recording was in progress', async () => {
    // Confirmed CodeRabbit finding on PR #134: the post-recording check
    // previously read the `user` this closure captured when
    // startRecording began, not the store's actual current state -- a
    // sign-out during the (up to MAX_DURATION_SEC) recording went
    // undetected, and the video queued/synced under a session that had
    // already ended.
    let resolveRecording: (r: { uri: string }) => void;
    mockRecordAsync.mockImplementation(
      () => new Promise((resolve) => { resolveRecording = resolve; }),
    );
    const { getByLabelText } = render(<RecordVideoScreen />);

    fireEvent.press(getByLabelText('Start recording'));
    setAuthUser(null); // signs out mid-recording
    await act(async () => {
      resolveRecording!({ uri: 'file:///tmp/clip.mov' });
    });

    expect(mockRecordVideo).not.toHaveBeenCalled();
    expect(mockToastShow).toHaveBeenCalledWith("Couldn't save your video — you're no longer signed in.");
  });

  it('does not sync under a different account that signed in while recordVideo was still saving', async () => {
    // Confirmed CodeRabbit finding on PR #136: `recordVideo` is itself
    // async, so the account checked at the top of the handler is not
    // guaranteed to still be signed in by the time it resolves. Syncing
    // anyway would authenticate the request as whoever is currently
    // signed in while attributing it to the account that started the
    // recording -- the same cross-account mistake this store's own
    // runSyncPass already guards against elsewhere.
    mockRecordAsync.mockResolvedValue({ uri: 'file:///tmp/clip.mov' });
    let resolveRecordVideo: () => void;
    mockRecordVideo.mockImplementation(
      () => new Promise((resolve) => { resolveRecordVideo = () => resolve(undefined); }),
    );
    const { getByLabelText } = render(<RecordVideoScreen />);

    fireEvent.press(getByLabelText('Start recording'));
    await act(async () => { await Promise.resolve(); }); // let recordAsync + the pre-save check settle
    setAuthUser({ id: 'user-2' }); // a different account signs in while recordVideo is still pending
    await act(async () => {
      resolveRecordVideo!();
    });

    expect(mockRecordVideo).toHaveBeenCalledWith(expect.objectContaining({ uploadedBy: 'user-1' }));
    expect(mockRunSyncPass).not.toHaveBeenCalled();
    expect(mockToastShow).toHaveBeenCalledWith("Saved — it'll post as soon as you're online.");
    expect(mockBack).toHaveBeenCalled();
  });

  it('defaults to video/mp4 for an unrecognized or missing extension', async () => {
    mockRecordAsync.mockResolvedValue({ uri: 'file:///tmp/clip' });
    const { getByLabelText } = render(<RecordVideoScreen />);

    await act(async () => {
      fireEvent.press(getByLabelText('Start recording'));
    });

    expect(mockRecordVideo).toHaveBeenCalledWith(
      expect.objectContaining({ contentType: 'video/mp4' }),
    );
  });

  it('toasts the failure message and stays on screen when saving the recording fails', async () => {
    mockRecordAsync.mockResolvedValue({ uri: 'file:///tmp/clip.mp4' });
    mockRecordVideo.mockRejectedValue(new Error('Disk full'));
    const { getByLabelText } = render(<RecordVideoScreen />);

    await act(async () => {
      fireEvent.press(getByLabelText('Start recording'));
    });

    expect(mockToastShow).toHaveBeenCalledWith('Disk full');
    expect(mockBack).not.toHaveBeenCalled();
  });

  it('closes without saving anything when the close button is pressed', () => {
    const { getByLabelText } = render(<RecordVideoScreen />);
    fireEvent.press(getByLabelText('Close'));

    expect(mockBack).toHaveBeenCalled();
    expect(mockRecordVideo).not.toHaveBeenCalled();
  });
});
