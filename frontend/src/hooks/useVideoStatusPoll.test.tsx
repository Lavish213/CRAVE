import React from 'react';
import { Text } from 'react-native';
import { act, render, waitFor } from '@testing-library/react-native';
import { fetchVideoStatus } from '../api/videos';
import { useVideoStatusPoll } from './useVideoStatusPoll';

jest.mock('../api/videos', () => ({
  fetchVideoStatus: jest.fn(),
}));

function Probe({ videoId }: { videoId?: string }) {
  const { status, error, rejectReason } = useVideoStatusPoll(videoId);
  return (
    <Text testID="status">
      {status ?? 'none'}|{error ?? 'none'}|{rejectReason ?? 'none'}
    </Text>
  );
}

describe('useVideoStatusPoll', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('polls non-terminal video statuses until an approved terminal status', async () => {
    (fetchVideoStatus as jest.Mock)
      .mockResolvedValueOnce({
        id: 'video-1', status: 'queued', rejectReason: null, durationMs: null,
        foodScore: null, thumbnailUrl: null, videoUrl: null,
      })
      .mockResolvedValueOnce({
        id: 'video-1', status: 'approved', rejectReason: null, durationMs: 9000,
        foodScore: 0.92, thumbnailUrl: 'https://cdn.example/thumb.jpg', videoUrl: 'https://cdn.example/video.mp4',
      });

    const { getByTestId } = render(<Probe videoId="video-1" />);

    await waitFor(() => expect(getByTestId('status').props.children.join('')).toBe('queued|none|none'));
    expect(fetchVideoStatus).toHaveBeenCalledTimes(1);

    await act(async () => {
      jest.advanceTimersByTime(4000);
      await Promise.resolve();
    });

    await waitFor(() => expect(getByTestId('status').props.children.join('')).toBe('approved|none|none'));
    expect(fetchVideoStatus).toHaveBeenCalledTimes(2);

    await act(async () => {
      jest.advanceTimersByTime(10000);
      await Promise.resolve();
    });
    expect(fetchVideoStatus).toHaveBeenCalledTimes(2);
  });

  it('surfaces a failed terminal status as an error and stops polling', async () => {
    (fetchVideoStatus as jest.Mock).mockResolvedValue({
      id: 'video-1', status: 'failed', rejectReason: 'Transcode failed', durationMs: null,
      foodScore: null, thumbnailUrl: null, videoUrl: null,
    });

    const { getByTestId } = render(<Probe videoId="video-1" />);

    await waitFor(() => expect(getByTestId('status').props.children.join('')).toBe('failed|Transcode failed|Transcode failed'));
    expect(fetchVideoStatus).toHaveBeenCalledTimes(1);

    await act(async () => {
      jest.advanceTimersByTime(10000);
      await Promise.resolve();
    });
    expect(fetchVideoStatus).toHaveBeenCalledTimes(1);
  });
});
