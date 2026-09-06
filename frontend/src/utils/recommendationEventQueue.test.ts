import AsyncStorage from '@react-native-async-storage/async-storage';
import { sendRecommendationEvents } from '../api/recommendationEvents';
import {
  _resetRecommendationEventQueueForTests,
  flushRecommendationEvents,
  logRecommendationEvent,
  logRecommendationEvents,
} from './recommendationEventQueue';

jest.mock('../api/recommendationEvents', () => ({
  sendRecommendationEvents: jest.fn().mockResolvedValue(undefined),
}));

jest.mock('@react-native-async-storage/async-storage', () => ({
  __esModule: true,
  default: {
    getItem: jest.fn().mockResolvedValue(null),
    setItem: jest.fn().mockResolvedValue(undefined),
    removeItem: jest.fn().mockResolvedValue(undefined),
  },
}));

const mockSend = sendRecommendationEvents as jest.Mock;
const mockStorage = AsyncStorage as jest.Mocked<typeof AsyncStorage>;

async function settleAsyncWork() {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

beforeEach(async () => {
  jest.useFakeTimers();
  _resetRecommendationEventQueueForTests();
  mockSend.mockReset();
  mockSend.mockResolvedValue(undefined);
  mockStorage.getItem.mockReset();
  mockStorage.getItem.mockResolvedValue(null);
  mockStorage.setItem.mockReset();
  mockStorage.setItem.mockResolvedValue(undefined);
  mockStorage.removeItem.mockReset();
  mockStorage.removeItem.mockResolvedValue(undefined);
  await settleAsyncWork();
});

afterEach(() => {
  _resetRecommendationEventQueueForTests();
  jest.useRealTimers();
});

describe('recommendation event queue', () => {
  it('batches best-effort impressions until the flush timer fires', async () => {
    logRecommendationEvent({ surface: 'feed', event_type: 'impression' });
    expect(mockSend).not.toHaveBeenCalled();

    jest.advanceTimersByTime(4000);
    await settleAsyncWork();

    expect(mockSend).toHaveBeenCalledTimes(1);
    expect(mockSend).toHaveBeenCalledWith([
      expect.objectContaining({ surface: 'feed', event_type: 'impression' }),
    ]);
  });

  it('attaches the same session_id to every event in one app session', async () => {
    logRecommendationEvent({ surface: 'feed', event_type: 'impression' });
    logRecommendationEvent({ surface: 'feed', event_type: 'click' });
    jest.advanceTimersByTime(4000);
    await settleAsyncWork();

    const [batch] = mockSend.mock.calls[0];
    expect(batch).toHaveLength(2);
    expect(batch[0].session_id).toBe(batch[1].session_id);
    expect(typeof batch[0].session_id).toBe('string');
  });

  it('flushes a full best-effort batch without waiting for the timer', async () => {
    logRecommendationEvents(Array.from({ length: 40 }, (_, i) => ({
      surface: 'feed' as const,
      event_type: 'impression' as const,
      position: i,
    })));

    await settleAsyncWork();
    expect(mockSend).toHaveBeenCalledTimes(1);
    expect(mockSend.mock.calls[0][0]).toHaveLength(40);
  });

  it('does not retry a failed impression batch because observations are best-effort', async () => {
    mockSend.mockRejectedValueOnce(new Error('offline'));
    logRecommendationEvent({ surface: 'search', event_type: 'impression' });

    jest.advanceTimersByTime(4000);
    await settleAsyncWork();
    expect(mockSend).toHaveBeenCalledTimes(1);

    jest.advanceTimersByTime(30_000);
    await settleAsyncWork();
    expect(mockSend).toHaveBeenCalledTimes(1);
  });

  it('persists a confirmed save before it is acknowledged by the server', async () => {
    logRecommendationEvent({
      surface: 'feed',
      event_type: 'save',
      place_id: 'place-1',
      client_event_id: 'save-1',
    });
    await settleAsyncWork();

    expect(mockStorage.setItem).toHaveBeenCalledWith(
      '@crave/recommendation-event-outbox/v1',
      expect.stringContaining('save-1'),
    );
  });

  it('retains a durable save after send failure and retries it later', async () => {
    mockSend.mockRejectedValueOnce(new Error('offline')).mockResolvedValue(undefined);

    logRecommendationEvent({
      surface: 'feed',
      event_type: 'save',
      place_id: 'place-1',
      client_event_id: 'save-1',
    });
    await settleAsyncWork();

    jest.advanceTimersByTime(4000);
    await settleAsyncWork();
    expect(mockSend).toHaveBeenCalledTimes(1);

    // Durable failures use a slower retry interval and keep the same
    // client_event_id so the backend's unique index makes resubmission safe.
    jest.advanceTimersByTime(15_000);
    await settleAsyncWork();

    expect(mockSend).toHaveBeenCalledTimes(2);
    expect(mockSend.mock.calls[1][0][0]).toEqual(
      expect.objectContaining({ client_event_id: 'save-1', event_type: 'save' }),
    );
    expect(mockStorage.removeItem).toHaveBeenCalledWith('@crave/recommendation-event-outbox/v1');
  });

  it('deduplicates a durable outcome by client_event_id before sending', async () => {
    const event = {
      surface: 'craves' as const,
      event_type: 'unsave' as const,
      place_id: 'place-1',
      client_event_id: 'unsave-1',
    };

    logRecommendationEvent(event);
    logRecommendationEvent(event);
    await settleAsyncWork();
    flushRecommendationEvents();
    await settleAsyncWork();

    expect(mockSend).toHaveBeenCalledTimes(1);
    expect(mockSend.mock.calls[0][0]).toHaveLength(1);
  });

  it('rehydrates a persisted durable outcome and sends it on explicit recovery flush', async () => {
    _resetRecommendationEventQueueForTests();
    mockStorage.getItem.mockResolvedValueOnce(JSON.stringify([
      {
        surface: 'feed',
        event_type: 'save',
        place_id: 'place-2',
        client_event_id: 'save-from-disk',
        session_id: 'old-session',
      },
    ]));

    flushRecommendationEvents();
    await settleAsyncWork();

    expect(mockSend).toHaveBeenCalledWith([
      expect.objectContaining({ client_event_id: 'save-from-disk' }),
    ]);
  });

  it('drops malformed persisted rows instead of poisoning every future flush', async () => {
    _resetRecommendationEventQueueForTests();
    mockStorage.getItem.mockResolvedValueOnce(JSON.stringify([
      { surface: 'feed', event_type: 'save', client_event_id: null },
      { nope: true },
    ]));

    flushRecommendationEvents();
    await settleAsyncWork();

    expect(mockSend).not.toHaveBeenCalled();
  });
});
