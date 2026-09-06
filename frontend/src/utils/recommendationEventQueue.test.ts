import AsyncStorage from '@react-native-async-storage/async-storage';
import { sendRecommendationEvents } from '../api/recommendationEvents';
import { supabase } from '../lib/supabase';
import {
  _resetRecommendationEventQueueForTests,
  flushRecommendationEvents,
  logRecommendationEvent,
  logRecommendationEvents,
} from './recommendationEventQueue';

jest.mock('../api/recommendationEvents', () => ({
  sendRecommendationEvents: jest.fn().mockResolvedValue(undefined),
}));

jest.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: jest.fn(),
    },
  },
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
const mockGetSession = supabase.auth.getSession as jest.Mock;

async function settleAsyncWork() {
  await Promise.resolve();
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
  mockGetSession.mockReset();
  mockGetSession.mockResolvedValue({ data: { session: { user: { id: 'user-a' } } } });
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

  it('persists a confirmed save with the authenticated owner before acknowledgment', async () => {
    logRecommendationEvent({
      surface: 'feed',
      event_type: 'save',
      place_id: 'place-1',
      client_event_id: 'save-1',
    });
    await settleAsyncWork();

    expect(mockStorage.setItem).toHaveBeenCalledWith(
      '@crave/recommendation-event-outbox/v1',
      expect.stringContaining('"ownerUserId":"user-a"'),
    );
    expect(mockStorage.setItem).toHaveBeenCalledWith(
      '@crave/recommendation-event-outbox/v1',
      expect.stringContaining('save-1'),
    );
  });

  it('keeps the mutation owner when Account A finishes after the ambient session switched to B', async () => {
    mockGetSession.mockResolvedValue({ data: { session: { user: { id: 'user-b' } } } });

    logRecommendationEvent(
      {
        surface: 'feed',
        event_type: 'save',
        place_id: 'place-a',
        client_event_id: 'save-a-race',
      },
      'user-a',
    );
    await settleAsyncWork();

    expect(mockStorage.setItem).toHaveBeenCalledWith(
      '@crave/recommendation-event-outbox/v1',
      expect.stringContaining('"ownerUserId":"user-a"'),
    );
    expect(mockStorage.setItem).not.toHaveBeenCalledWith(
      '@crave/recommendation-event-outbox/v1',
      expect.stringContaining('"ownerUserId":"user-b"'),
    );
  });

  it('retains a durable save after send failure and retries it later', async () => {
    mockSend.mockRejectedValueOnce(new Error('offline')).mockResolvedValue(undefined);

    logRecommendationEvent({
      surface: 'feed',
      event_type: 'save',
      place_id: 'place-1',
      client_event_id: 'save-1',
    }, 'user-a');
    await settleAsyncWork();

    // Force the first delivery attempt and await the complete failure path,
    // including scheduling the 15s durable retry. This avoids advancing the
    // clock before the async outbox persistence/auth lookup has finished.
    await flushRecommendationEvents();
    expect(mockSend).toHaveBeenCalledTimes(1);

    await jest.advanceTimersByTimeAsync(15_000);
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

    logRecommendationEvent(event, 'user-a');
    logRecommendationEvent(event, 'user-a');
    await settleAsyncWork();
    await flushRecommendationEvents();

    expect(mockSend).toHaveBeenCalledTimes(1);
    expect(mockSend.mock.calls[0][0]).toHaveLength(1);
  });

  it('does not send Account A durable events while Account B is authenticated', async () => {
    _resetRecommendationEventQueueForTests();
    mockStorage.getItem.mockResolvedValueOnce(JSON.stringify([
      {
        ownerUserId: 'user-a',
        event: {
          surface: 'feed',
          event_type: 'save',
          place_id: 'place-a',
          client_event_id: 'save-a',
          session_id: 'old-session',
        },
      },
    ]));
    mockGetSession.mockResolvedValue({ data: { session: { user: { id: 'user-b' } } } });

    await flushRecommendationEvents();

    expect(mockSend).not.toHaveBeenCalled();
    expect(mockStorage.removeItem).not.toHaveBeenCalled();
  });

  it('rehydrates and sends the durable event once its owning account returns', async () => {
    _resetRecommendationEventQueueForTests();
    mockStorage.getItem.mockResolvedValueOnce(JSON.stringify([
      {
        ownerUserId: 'user-a',
        event: {
          surface: 'feed',
          event_type: 'save',
          place_id: 'place-a',
          client_event_id: 'save-a',
          session_id: 'old-session',
        },
      },
    ]));
    mockGetSession.mockResolvedValue({ data: { session: { user: { id: 'user-a' } } } });

    await flushRecommendationEvents();

    expect(mockSend).toHaveBeenCalledWith([
      expect.objectContaining({ client_event_id: 'save-a' }),
    ]);
  });

  it('drops malformed persisted rows instead of poisoning future flushes', async () => {
    _resetRecommendationEventQueueForTests();
    mockStorage.getItem.mockResolvedValueOnce(JSON.stringify([
      { ownerUserId: 'user-a', event: { surface: 'feed', event_type: 'save', client_event_id: null } },
      { nope: true },
    ]));

    await flushRecommendationEvents();

    expect(mockSend).not.toHaveBeenCalled();
  });
});
