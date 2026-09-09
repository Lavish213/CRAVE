jest.mock('@react-native-async-storage/async-storage', () => ({
  __esModule: true,
  default: {
    getItem: jest.fn(() => Promise.resolve(null)),
    setItem: jest.fn(() => Promise.resolve()),
    removeItem: jest.fn(() => Promise.resolve()),
  },
}));

jest.mock('expo-file-system/legacy', () => ({
  documentDirectory: 'file:///mock-docs/',
  makeDirectoryAsync: jest.fn(() => Promise.resolve()),
  moveAsync: jest.fn(() => Promise.resolve()),
  deleteAsync: jest.fn(() => Promise.resolve()),
}));

jest.mock('../api/upload', () => {
  const actual = jest.requireActual('../api/upload');
  return {
    ...actual,
    requestUpload: jest.fn(),
    uploadToSignedUrl: jest.fn(),
    confirmUpload: jest.fn(),
  };
});

jest.mock('../api/nearby', () => ({
  getCandidateStatus: jest.fn(),
}));

jest.mock('./videoQueueStore', () => ({
  useVideoQueueStore: { getState: () => ({ recordVideo: jest.fn() }) },
}));

jest.mock('../hooks/useToast', () => ({
  useToast: { getState: () => ({ show: jest.fn() }) },
}));

describe('Posting V2 composer draft semantics', () => {
  let usePostingDraftStore: typeof import('./postingDraftStore').usePostingDraftStore;

  beforeEach(() => {
    jest.resetModules();
    ({ usePostingDraftStore } = require('./postingDraftStore'));
  });

  async function createDraft(intent?: 'private_log' | 'social_post') {
    return usePostingDraftStore.getState().createDraftFromCapture({
      ownerId: 'user-a',
      sourceUri: 'file:///tmp/food.jpg',
      kind: 'photo',
      mimeType: 'image/jpeg',
      fileSize: 500_000,
      intent,
    });
  }

  it('creates a private-log draft with an explicit private visibility floor', async () => {
    const draft = await createDraft('private_log');

    expect(draft.intent).toBe('private_log');
    expect(draft.visibility).toBe('private');
    expect(draft.reaction).toBeNull();
    expect(draft.caption).toBe('');
    expect(draft.occurredAt).toBeNull();
    expect(draft.updatedAt).toBe(draft.createdAt);
  });

  it('creates a social-post draft with visibility deliberately unset', async () => {
    const draft = await createDraft('social_post');

    expect(draft.intent).toBe('social_post');
    expect(draft.visibility).toBeNull();
  });

  it('never represents a private log with public or connections visibility', async () => {
    const draft = await createDraft('private_log');

    usePostingDraftStore.getState().setDraftVisibility(draft.id, 'public');
    expect(usePostingDraftStore.getState().drafts[0]?.visibility).toBe('private');

    usePostingDraftStore.getState().setDraftVisibility(draft.id, 'connections');
    expect(usePostingDraftStore.getState().drafts[0]?.visibility).toBe('private');
  });

  it('requires an explicit social audience again after switching from private logging', async () => {
    const draft = await createDraft('social_post');
    usePostingDraftStore.getState().setDraftVisibility(draft.id, 'public');
    expect(usePostingDraftStore.getState().drafts[0]?.visibility).toBe('public');

    usePostingDraftStore.getState().setDraftIntent(draft.id, 'private_log');
    expect(usePostingDraftStore.getState().drafts[0]?.visibility).toBe('private');

    usePostingDraftStore.getState().setDraftIntent(draft.id, 'social_post');
    expect(usePostingDraftStore.getState().drafts[0]?.visibility).toBeNull();
  });

  it('stores structured reaction, caption, and visit time without inferring any of them', async () => {
    const draft = await createDraft('private_log');
    const occurredAt = '2026-09-08T19:30:00.000Z';

    usePostingDraftStore.getState().setDraftReaction(draft.id, 'not_for_me');
    usePostingDraftStore.getState().setDraftCaption(draft.id, 'Too salty for me.');
    usePostingDraftStore.getState().setDraftOccurredAt(draft.id, occurredAt);

    const stored = usePostingDraftStore.getState().drafts[0];
    expect(stored?.reaction).toBe('not_for_me');
    expect(stored?.caption).toBe('Too salty for me.');
    expect(stored?.occurredAt).toBe(occurredAt);
  });

  it('allows reaction to be explicitly cleared rather than treating missing reaction as positive', async () => {
    const draft = await createDraft('private_log');

    usePostingDraftStore.getState().setDraftReaction(draft.id, 'loved');
    usePostingDraftStore.getState().setDraftReaction(draft.id, null);

    expect(usePostingDraftStore.getState().drafts[0]?.reaction).toBeNull();
  });
});
