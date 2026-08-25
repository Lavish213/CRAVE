import { sendRecommendationEvents } from '../api/recommendationEvents';
import { logRecommendationEvent, logRecommendationEvents } from './recommendationEventQueue';

jest.mock('../api/recommendationEvents', () => ({
  sendRecommendationEvents: jest.fn().mockResolvedValue(undefined),
}));

const mockSend = sendRecommendationEvents as jest.Mock;

beforeEach(() => {
  jest.useFakeTimers();
  mockSend.mockClear();
});

afterEach(() => {
  // Drain any pending timer so state doesn't leak into the next test.
  jest.runOnlyPendingTimers();
  jest.useRealTimers();
});

describe('logRecommendationEvent', () => {
  it('does not send immediately -- batches until the flush timer fires', () => {
    logRecommendationEvent({ surface: 'feed', event_type: 'impression' });
    expect(mockSend).not.toHaveBeenCalled();

    jest.advanceTimersByTime(4000);

    expect(mockSend).toHaveBeenCalledTimes(1);
    expect(mockSend).toHaveBeenCalledWith([
      expect.objectContaining({ surface: 'feed', event_type: 'impression' }),
    ]);
  });

  it('attaches the same session_id to every event in a session', () => {
    logRecommendationEvent({ surface: 'feed', event_type: 'impression' });
    logRecommendationEvent({ surface: 'feed', event_type: 'click' });
    jest.advanceTimersByTime(4000);

    const [batch] = mockSend.mock.calls[0];
    expect(batch).toHaveLength(2);
    expect(batch[0].session_id).toBe(batch[1].session_id);
    expect(typeof batch[0].session_id).toBe('string');
  });

  it('flushes immediately once the queue reaches the max batch size, without waiting for the timer', () => {
    const events = Array.from({ length: 40 }, (_, i) => ({
      surface: 'feed' as const,
      event_type: 'impression' as const,
      position: i,
    }));
    logRecommendationEvents(events);

    // No jest.advanceTimersByTime() call at all -- the size threshold
    // alone must have triggered the flush.
    expect(mockSend).toHaveBeenCalledTimes(1);
    expect(mockSend.mock.calls[0][0]).toHaveLength(40);
  });

  it('does not re-send an already-flushed batch when the timer later fires', () => {
    logRecommendationEvent({ surface: 'search', event_type: 'impression' });
    jest.advanceTimersByTime(4000);
    expect(mockSend).toHaveBeenCalledTimes(1);

    // Nothing new queued -- advancing further must not produce another call.
    jest.advanceTimersByTime(10000);
    expect(mockSend).toHaveBeenCalledTimes(1);
  });
});
