// Uploads screen (app/uploads.tsx) -- first dedicated coverage. Locks in:
// signed-out gate, the honest empty state, filtering to the signed-in
// user's own non-synced videos/drafts, and wiring the already-built-but-
// previously-dead retryFailedVideo/deleteFailedVideo/attachDraftToPlace-
// retry/deleteDraft into real buttons.
import React from 'react';
import { Alert } from 'react-native';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import UploadsScreen from '../app/uploads';
import { useAuthStore } from '../src/stores/authStore';
import { useVideoQueueStore, QueuedVideo } from '../src/stores/videoQueueStore';
import { usePostingDraftStore, PostingDraft } from '../src/stores/postingDraftStore';
import { fetchVideoStatus } from '../src/api/videos';

let mockUser: { id: string } | null = { id: 'user-1' };
jest.mock('../src/stores/authStore', () => ({
  useAuthStore: (selector: (s: { user: typeof mockUser }) => unknown) => selector({ user: mockUser }),
}));

// videoQueueStore.ts itself imports requestVideoUpload/confirmVideoUpload/
// uploadVideoToSignedUrl from this same module -- stubbed here too so the
// store still imports cleanly, even though this file's own tests never
// exercise the real sync path (videos are seeded directly via setState).
jest.mock('../src/api/videos', () => ({
  fetchVideoStatus: jest.fn(),
  requestVideoUpload: jest.fn(),
  confirmVideoUpload: jest.fn(),
  uploadVideoToSignedUrl: jest.fn(),
}));
const mockedFetchVideoStatus = fetchVideoStatus as jest.MockedFunction<typeof fetchVideoStatus>;

function pressAlertButton(buttonText: string) {
  const call = (Alert.alert as jest.Mock).mock.calls[(Alert.alert as jest.Mock).mock.calls.length - 1];
  const buttons = call[2] as { text: string; onPress?: () => void }[];
  buttons.find((b) => b.text === buttonText)?.onPress?.();
}

function makeVideo(overrides: Partial<QueuedVideo>): QueuedVideo {
  return {
    id: 'v1', serverId: null, localUri: 'file:///v1.mp4', placeId: 'place-1', templateId: null,
    contentType: 'video/mp4', uploadedBy: 'user-1', syncState: 'recorded', attemptCount: 0,
    lastAttemptAt: null, lastError: null, createdAt: Date.now(), ...overrides,
  };
}

function makeDraft(overrides: Partial<PostingDraft>): PostingDraft {
  return {
    id: 'd1', ownerId: 'user-1', localUri: 'file:///d1.jpg', kind: 'photo', mimeType: 'image/jpeg',
    fileSize: 100, restaurantRef: { type: 'unresolved' }, outcome: 'pending', lastError: null,
    createdAt: Date.now(), ...overrides,
  };
}

describe('UploadsScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(Alert, 'alert').mockImplementation(() => {});
    mockUser = { id: 'user-1' };
    useVideoQueueStore.setState({ videos: [] });
    usePostingDraftStore.setState({ drafts: [] });
  });

  it('gates a signed-out viewer without reading either store', () => {
    mockUser = null;
    useVideoQueueStore.setState({ videos: [makeVideo({ syncState: 'failed' })] });
    const { getByText } = render(<UploadsScreen />);
    expect(getByText('Sign in to see your uploads')).toBeTruthy();
  });

  it('shows an honest empty state when nothing is pending', () => {
    const { getByText } = render(<UploadsScreen />);
    expect(getByText('Nothing pending')).toBeTruthy();
  });

  it('excludes synced videos and other users\' videos/drafts', () => {
    useVideoQueueStore.setState({
      videos: [
        makeVideo({ id: 'synced', syncState: 'synced' }),
        makeVideo({ id: 'other-user', uploadedBy: 'someone-else', syncState: 'failed' }),
      ],
    });
    usePostingDraftStore.setState({ drafts: [makeDraft({ id: 'other-draft', ownerId: 'someone-else' })] });
    const { getByText } = render(<UploadsScreen />);
    expect(getByText('Nothing pending')).toBeTruthy();
  });

  it('retries a failed video via the already-built retryFailedVideo + a fresh sync pass', () => {
    useVideoQueueStore.setState({
      videos: [makeVideo({ syncState: 'failed', attemptCount: 5, lastError: 'Network Error' })],
    });
    const runSyncPassSpy = jest.spyOn(useVideoQueueStore.getState(), 'runSyncPass').mockResolvedValue(undefined);

    const { getByText, getByLabelText } = render(<UploadsScreen />);
    expect(getByText('Network Error')).toBeTruthy();

    fireEvent.press(getByLabelText('Retry upload'));

    expect(useVideoQueueStore.getState().videos[0].syncState).toBe('recorded');
    expect(useVideoQueueStore.getState().videos[0].attemptCount).toBe(0);
    expect(runSyncPassSpy).toHaveBeenCalledWith('user-1');
  });

  it('deletes a failed video only after confirming', async () => {
    useVideoQueueStore.setState({ videos: [makeVideo({ syncState: 'failed' })] });
    const { getByLabelText, queryByLabelText } = render(<UploadsScreen />);

    fireEvent.press(getByLabelText('Delete video'));
    expect(useVideoQueueStore.getState().videos).toHaveLength(1); // not yet -- awaiting confirmation

    pressAlertButton('Delete');
    await waitFor(() => expect(useVideoQueueStore.getState().videos).toHaveLength(0));
    expect(queryByLabelText('Delete video')).toBeNull();
  });

  it('does not delete a video when the confirmation is cancelled', () => {
    useVideoQueueStore.setState({ videos: [makeVideo({ syncState: 'missing_local_file' })] });
    const { getByLabelText } = render(<UploadsScreen />);

    fireEvent.press(getByLabelText('Delete video'));
    pressAlertButton('Cancel');
    expect(useVideoQueueStore.getState().videos).toHaveLength(1);
  });

  it('shows a candidate draft as waiting for corroboration, with no retry control', () => {
    usePostingDraftStore.setState({
      drafts: [makeDraft({ restaurantRef: { type: 'candidate', candidateId: 'c1', displayName: 'Tia Rosa' } })],
    });
    const { getByText, queryByLabelText } = render(<UploadsScreen />);
    expect(getByText('Waiting for "Tia Rosa" to be confirmed')).toBeTruthy();
    expect(queryByLabelText('Retry')).toBeNull();
  });

  it('retries a failed draft via the already-built attachDraftToPlace, using its retained placeId', async () => {
    usePostingDraftStore.setState({
      drafts: [makeDraft({
        outcome: 'failed', lastError: "Couldn't attach", restaurantRef: { type: 'place', placeId: 'place-9' },
      })],
    });
    const attachSpy = jest
      .spyOn(usePostingDraftStore.getState(), 'attachDraftToPlace')
      .mockResolvedValue(true);

    const { getByLabelText } = render(<UploadsScreen />);
    fireEvent.press(getByLabelText('Retry'));

    await waitFor(() => expect(attachSpy).toHaveBeenCalledWith('d1', 'place-9', 'user-1'));
  });

  it('deletes a draft only after confirming', () => {
    usePostingDraftStore.setState({ drafts: [makeDraft({})] });
    const deleteSpy = jest.spyOn(usePostingDraftStore.getState(), 'deleteDraft').mockResolvedValue(undefined);

    const { getByLabelText } = render(<UploadsScreen />);
    fireEvent.press(getByLabelText('Delete'));
    expect(deleteSpy).not.toHaveBeenCalled();

    pressAlertButton('Delete');
    expect(deleteSpy).toHaveBeenCalledWith('d1');
  });

  describe('per-video review-status polling', () => {
    it('shows a reviewing video as under review, with no Retry/Delete controls', () => {
      mockedFetchVideoStatus.mockResolvedValue({
        id: 'server-1', status: 'processing', rejectReason: null, durationMs: null,
        foodScore: null, thumbnailUrl: null, videoUrl: null,
      });
      useVideoQueueStore.setState({
        videos: [makeVideo({ syncState: 'reviewing', serverId: 'server-1' })],
      });

      const { getByText, queryByLabelText } = render(<UploadsScreen />);
      expect(getByText('Uploaded — under review')).toBeTruthy();
      expect(queryByLabelText('Retry upload')).toBeNull();
      expect(queryByLabelText('Delete video')).toBeNull();
    });

    it('polls fetchVideoStatus for a reviewing video and removes it once approved', async () => {
      mockedFetchVideoStatus.mockResolvedValue({
        id: 'server-1', status: 'approved', rejectReason: null, durationMs: null,
        foodScore: null, thumbnailUrl: null, videoUrl: null,
      });
      useVideoQueueStore.setState({
        videos: [makeVideo({ syncState: 'reviewing', serverId: 'server-1' })],
      });

      const { getByText, queryByText } = render(<UploadsScreen />);
      expect(getByText('Uploaded — under review')).toBeTruthy();

      await waitFor(() => expect(mockedFetchVideoStatus).toHaveBeenCalledWith('server-1'));
      await waitFor(() => expect(useVideoQueueStore.getState().videos[0].syncState).toBe('synced'));
      // 'synced' is filtered out of the visible list -- approval removes
      // the row from view entirely rather than leaving a dead "Uploaded"
      // entry behind.
      await waitFor(() => expect(queryByText('Uploaded — under review')).toBeNull());
    });

    it('polls fetchVideoStatus for a reviewing video and surfaces the reject reason once rejected, with only a Delete control', async () => {
      mockedFetchVideoStatus.mockResolvedValue({
        id: 'server-1', status: 'rejected', rejectReason: 'No food visible', durationMs: null,
        foodScore: null, thumbnailUrl: null, videoUrl: null,
      });
      useVideoQueueStore.setState({
        videos: [makeVideo({ syncState: 'reviewing', serverId: 'server-1' })],
      });

      const { findByText, queryByLabelText, getByLabelText } = render(<UploadsScreen />);
      expect(await findByText('No food visible')).toBeTruthy();
      expect(queryByLabelText('Retry upload')).toBeNull(); // rejected content isn't retryable
      expect(getByLabelText('Delete video')).toBeTruthy();
    });

    it('does not poll a video that is not reviewing', () => {
      useVideoQueueStore.setState({
        videos: [makeVideo({ syncState: 'failed', serverId: 'server-1', lastError: 'Network Error' })],
      });
      render(<UploadsScreen />);
      expect(mockedFetchVideoStatus).not.toHaveBeenCalled();
    });

    it('surfaces a persistent polling failure instead of leaving the row silently stuck on "under review"', async () => {
      // Confirmed CodeRabbit finding on PR #310: useVideoStatusPoll retried
      // a failing fetchVideoStatus call forever with nothing surfaced --
      // this row must show something once a check actually fails, not
      // stay indistinguishable from a normal in-progress review.
      mockedFetchVideoStatus.mockRejectedValue(new Error('Network request failed'));
      useVideoQueueStore.setState({
        videos: [makeVideo({ syncState: 'reviewing', serverId: 'server-1' })],
      });

      const { findByText, queryByText } = render(<UploadsScreen />);
      expect(await findByText("Couldn't check status — retrying…")).toBeTruthy();
      // Not the normal in-progress copy while a check is actively failing.
      expect(queryByText('Uploaded — under review')).toBeNull();
    });

    it('clears a prior polling failure once a status check succeeds again', async () => {
      mockedFetchVideoStatus.mockRejectedValueOnce(new Error('Network request failed'));
      mockedFetchVideoStatus.mockResolvedValueOnce({
        id: 'server-1', status: 'processing', rejectReason: null, durationMs: null,
        foodScore: null, thumbnailUrl: null, videoUrl: null,
      });
      useVideoQueueStore.setState({
        videos: [makeVideo({ syncState: 'reviewing', serverId: 'server-1' })],
      });

      const { findByText } = render(<UploadsScreen />);
      expect(await findByText("Couldn't check status — retrying…")).toBeTruthy();

      // The hook's own real backoff (2s) elapses before its retry fires --
      // waited out in real time here (a generous findByText timeout)
      // rather than fake timers, which would fight RTL's own internal
      // polling for the same clock.
      expect(await findByText('Uploaded — under review', {}, { timeout: 4000 })).toBeTruthy();
    }, 10000);
  });
});
