jest.mock('@react-native-async-storage/async-storage', () => ({
  __esModule: true,
  default: { getItem: jest.fn(() => Promise.resolve(null)), setItem: jest.fn(() => Promise.resolve()), removeItem: jest.fn(() => Promise.resolve()) },
}));
jest.mock('expo-file-system/legacy', () => ({
  documentDirectory: 'file:///mock-docs/', makeDirectoryAsync: jest.fn(() => Promise.resolve()), moveAsync: jest.fn(() => Promise.resolve()), deleteAsync: jest.fn(() => Promise.resolve()),
}));
jest.mock('../api/nearby', () => ({ getCandidateStatus: jest.fn() }));

describe('postingDraftStore explicit-commit architecture', () => {
  let store: typeof import('./postingDraftStore').usePostingDraftStore;
  let nearby: typeof import('../api/nearby');
  let fs: typeof import('expo-file-system/legacy');

  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
    nearby = require('../api/nearby');
    fs = require('expo-file-system/legacy');
    ({ usePostingDraftStore: store } = require('./postingDraftStore'));
  });

  async function draft(ownerId = 'user-a') {
    return store.getState().createDraftFromCapture({ ownerId, sourceUri: 'file:///tmp/food.jpg', kind: 'photo', mimeType: 'image/jpeg', fileSize: 500_000 });
  }

  it('persists capture locally before restaurant or publication semantics', async () => {
    const d = await draft();
    expect(d.restaurantRef).toEqual({ type: 'unresolved' });
    expect(d.intent).toBeNull();
    expect(d.visibility).toBeNull();
    expect(fs.moveAsync).toHaveBeenCalledTimes(1);
  });

  it('resolves an existing place without uploading or deleting the draft', async () => {
    const d = await draft();
    store.getState().setDraftPlace(d.id, 'place-1');
    const saved = store.getState().drafts.find((x) => x.id === d.id);
    expect(saved?.restaurantRef).toEqual({ type: 'place', placeId: 'place-1' });
    expect(saved?.outcome).toBe('pending');
    expect(store.getState().drafts).toHaveLength(1);
  });

  it('keeps private-log visibility structurally private', async () => {
    const d = await draft();
    store.getState().setDraftIntent(d.id, 'private_log');
    store.getState().setDraftVisibility(d.id, 'public');
    expect(store.getState().drafts[0]?.visibility).toBe('private');
  });

  it('requires social audience to be reselected after switching from private', async () => {
    const d = await draft();
    store.getState().setDraftIntent(d.id, 'private_log');
    store.getState().setDraftIntent(d.id, 'social_post');
    expect(store.getState().drafts[0]?.visibility).toBeNull();
  });

  it('candidate promotion resolves identity only and preserves media/composer state', async () => {
    (nearby.getCandidateStatus as jest.Mock).mockResolvedValue({ candidate_id: 'cand-1', resolved: true, place_id: 'place-9', blocked: false });
    const d = await draft();
    store.getState().setDraftIntent(d.id, 'private_log');
    store.getState().setDraftReaction(d.id, 'loved');
    store.getState().setDraftCandidate(d.id, 'cand-1', 'New Place');

    await store.getState().resolvePendingCandidates('user-a');

    const saved = store.getState().drafts.find((x) => x.id === d.id);
    expect(saved?.restaurantRef).toEqual({ type: 'place', placeId: 'place-9' });
    expect(saved?.reaction).toBe('loved');
    expect(store.getState().drafts).toHaveLength(1);
  });

  it('does not resolve another account’s candidate draft', async () => {
    const d = await draft('user-b');
    store.getState().setDraftCandidate(d.id, 'cand-1', 'New Place');
    await store.getState().resolvePendingCandidates('user-a');
    expect(nearby.getCandidateStatus).not.toHaveBeenCalled();
  });

  it('deletes local media only on explicit draft deletion', async () => {
    const d = await draft();
    await store.getState().deleteDraft(d.id);
    expect(fs.deleteAsync).toHaveBeenCalledWith(d.localUri, { idempotent: true });
    expect(store.getState().drafts).toHaveLength(0);
  });
});
