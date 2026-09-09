// Regression coverage for postingDraftStore.ts's capture-durably/attach-
// later flow -- mirrors videoQueueStore.test.ts's mocking conventions.
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

const mockRecordVideo = jest.fn();
jest.mock('./videoQueueStore', () => ({
  useVideoQueueStore: { getState: () => ({ recordVideo: mockRecordVideo }) },
}));

const mockToastShow = jest.fn();
jest.mock('../hooks/useToast', () => ({
  useToast: { getState: () => ({ show: mockToastShow }) },
}));

describe('postingDraftStore', () => {
  let usePostingDraftStore: typeof import('./postingDraftStore').usePostingDraftStore;
  let uploadApi: typeof import('../api/upload');
  let nearbyApi: typeof import('../api/nearby');
  let FileSystem: typeof import('expo-file-system/legacy');

  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
    uploadApi = require('../api/upload');
    nearbyApi = require('../api/nearby');
    FileSystem = require('expo-file-system/legacy');
    (FileSystem.moveAsync as jest.Mock).mockClear();
    (FileSystem.deleteAsync as jest.Mock).mockClear();
    ({ usePostingDraftStore } = require('./postingDraftStore'));
  });

  it('creates a draft locally without touching the network, with restaurantRef unresolved', async () => {
    const draft = await usePostingDraftStore.getState().createDraftFromCapture({
      ownerId: 'user-a',
      sourceUri: 'file:///tmp/camera-output.jpg',
      kind: 'photo',
      mimeType: 'image/jpeg',
      fileSize: 500_000,
    });

    expect(draft.restaurantRef).toEqual({ type: 'unresolved' });
    expect(draft.outcome).toBe('pending');
    expect(FileSystem.moveAsync).toHaveBeenCalledTimes(1);
    expect(uploadApi.requestUpload).not.toHaveBeenCalled();
    expect(usePostingDraftStore.getState().drafts).toHaveLength(1);
  });

  it('attaches a photo draft to a place via request -> PUT -> confirm, then removes the draft', async () => {
    (uploadApi.requestUpload as jest.Mock).mockResolvedValue({ image_id: 'img-1', upload_url: 'https://r2.example.test/put' });
    (uploadApi.uploadToSignedUrl as jest.Mock).mockResolvedValue(undefined);
    (uploadApi.confirmUpload as jest.Mock).mockResolvedValue({ ok: true });

    const draft = await usePostingDraftStore.getState().createDraftFromCapture({
      ownerId: 'user-a',
      sourceUri: 'file:///tmp/photo.jpg',
      kind: 'photo',
      mimeType: 'image/jpeg',
      fileSize: 500_000,
    });

    await usePostingDraftStore.getState().attachDraftToPlace(draft.id, 'place-1');

    expect(uploadApi.requestUpload).toHaveBeenCalledWith({
      place_id: 'place-1',
      content_type: 'image/jpeg',
      file_size_mb: expect.any(Number),
      photo_type: 'food',
    });
    expect(uploadApi.confirmUpload).toHaveBeenCalledWith('img-1');
    expect(FileSystem.deleteAsync).toHaveBeenCalledWith(draft.localUri, { idempotent: true });
    expect(mockToastShow).toHaveBeenCalledWith('Photo submitted for this place');
    expect(usePostingDraftStore.getState().drafts).toHaveLength(0);
  });

  it('attaches a video draft by handing off to videoQueueStore.recordVideo, then removes the draft', async () => {
    mockRecordVideo.mockResolvedValue({ id: 'local-1' });

    const draft = await usePostingDraftStore.getState().createDraftFromCapture({
      ownerId: 'user-a',
      sourceUri: 'file:///tmp/clip.mov',
      kind: 'video',
    });

    await usePostingDraftStore.getState().attachDraftToPlace(draft.id, 'place-1');

    expect(mockRecordVideo).toHaveBeenCalledWith({
      sourceUri: draft.localUri,
      placeId: 'place-1',
      contentType: 'video/quicktime',
      uploadedBy: 'user-a',
      templateId: null,
    });
    expect(mockToastShow).toHaveBeenCalledWith("Saved — it'll post as soon as you're online.");
    expect(usePostingDraftStore.getState().drafts).toHaveLength(0);
  });

  it('marks a draft failed (not crashing) when the attach itself fails, keeping the draft around', async () => {
    (uploadApi.requestUpload as jest.Mock).mockRejectedValue(new Error('Upload to storage failed'));

    const draft = await usePostingDraftStore.getState().createDraftFromCapture({
      ownerId: 'user-a',
      sourceUri: 'file:///tmp/photo.jpg',
      kind: 'photo',
      mimeType: 'image/jpeg',
      fileSize: 500_000,
    });

    await usePostingDraftStore.getState().attachDraftToPlace(draft.id, 'place-1');

    const stored = usePostingDraftStore.getState().drafts.find((d) => d.id === draft.id);
    expect(stored?.outcome).toBe('failed');
    expect(stored?.lastError).toBe('Upload to storage failed');
    expect(mockToastShow).toHaveBeenCalledWith('Upload to storage failed');
  });

  it('does not double-attach the same draft when attachDraftToPlace is called twice back-to-back', async () => {
    (uploadApi.requestUpload as jest.Mock).mockResolvedValue({ image_id: 'img-1', upload_url: 'https://r2.example.test/put' });
    (uploadApi.uploadToSignedUrl as jest.Mock).mockResolvedValue(undefined);
    (uploadApi.confirmUpload as jest.Mock).mockResolvedValue({ ok: true });

    const draft = await usePostingDraftStore.getState().createDraftFromCapture({
      ownerId: 'user-a',
      sourceUri: 'file:///tmp/photo.jpg',
      kind: 'photo',
      mimeType: 'image/jpeg',
      fileSize: 500_000,
    });

    const first = usePostingDraftStore.getState().attachDraftToPlace(draft.id, 'place-a');
    const second = usePostingDraftStore.getState().attachDraftToPlace(draft.id, 'place-b');
    await Promise.all([first, second]);

    expect(uploadApi.requestUpload).toHaveBeenCalledTimes(1);
    expect(uploadApi.requestUpload).toHaveBeenCalledWith(expect.objectContaining({ place_id: 'place-a' }));
  });

  it('setDraftCandidate claims the draft for candidate resolution without attaching anything', async () => {
    const draft = await usePostingDraftStore.getState().createDraftFromCapture({
      ownerId: 'user-a',
      sourceUri: 'file:///tmp/photo.jpg',
      kind: 'photo',
      mimeType: 'image/jpeg',
      fileSize: 500_000,
    });

    usePostingDraftStore.getState().setDraftCandidate(draft.id, 'cand-1', "Mama Rosa's Taco Truck");

    const stored = usePostingDraftStore.getState().drafts.find((d) => d.id === draft.id);
    expect(stored?.restaurantRef).toEqual({ type: 'candidate', candidateId: 'cand-1', displayName: "Mama Rosa's Taco Truck" });
    expect(stored?.outcome).toBe('awaiting_place');
    expect(uploadApi.requestUpload).not.toHaveBeenCalled();
  });

  it('does not let an existing-place action steal media after a candidate has claimed the draft', async () => {
    const draft = await usePostingDraftStore.getState().createDraftFromCapture({
      ownerId: 'user-a',
      sourceUri: 'file:///tmp/photo.jpg',
      kind: 'photo',
      mimeType: 'image/jpeg',
      fileSize: 500_000,
    });

    usePostingDraftStore.getState().setDraftCandidate(draft.id, 'cand-1', 'New Place');
    await usePostingDraftStore.getState().attachDraftToPlace(draft.id, 'place-wrong');

    const stored = usePostingDraftStore.getState().drafts.find((d) => d.id === draft.id);
    expect(stored?.restaurantRef).toEqual({ type: 'candidate', candidateId: 'cand-1', displayName: 'New Place' });
    expect(stored?.outcome).toBe('awaiting_place');
    expect(uploadApi.requestUpload).not.toHaveBeenCalled();
    expect(mockRecordVideo).not.toHaveBeenCalled();
  });

  describe('resolvePendingCandidates', () => {
    it('auto-attaches a candidate draft once the backend reports it resolved to a place', async () => {
      (uploadApi.requestUpload as jest.Mock).mockResolvedValue({ image_id: 'img-1', upload_url: 'https://r2.example.test/put' });
      (uploadApi.uploadToSignedUrl as jest.Mock).mockResolvedValue(undefined);
      (uploadApi.confirmUpload as jest.Mock).mockResolvedValue({ ok: true });
      (nearbyApi.getCandidateStatus as jest.Mock).mockResolvedValue({
        candidate_id: 'cand-1', resolved: true, place_id: 'place-9', blocked: false,
      });

      const draft = await usePostingDraftStore.getState().createDraftFromCapture({
        ownerId: 'user-a',
        sourceUri: 'file:///tmp/photo.jpg',
        kind: 'photo',
        mimeType: 'image/jpeg',
        fileSize: 500_000,
      });
      usePostingDraftStore.getState().setDraftCandidate(draft.id, 'cand-1', 'New Place');

      await usePostingDraftStore.getState().resolvePendingCandidates('user-a');

      expect(nearbyApi.getCandidateStatus).toHaveBeenCalledWith('cand-1');
      expect(uploadApi.requestUpload).toHaveBeenCalledWith(expect.objectContaining({ place_id: 'place-9' }));
      expect(usePostingDraftStore.getState().drafts).toHaveLength(0);
    });

    it('leaves a still-unresolved candidate draft awaiting place promotion, untouched', async () => {
      (nearbyApi.getCandidateStatus as jest.Mock).mockResolvedValue({
        candidate_id: 'cand-1', resolved: false, place_id: null, blocked: false,
      });

      const draft = await usePostingDraftStore.getState().createDraftFromCapture({
        ownerId: 'user-a',
        sourceUri: 'file:///tmp/photo.jpg',
        kind: 'photo',
        mimeType: 'image/jpeg',
        fileSize: 500_000,
      });
      usePostingDraftStore.getState().setDraftCandidate(draft.id, 'cand-1', 'New Place');

      await usePostingDraftStore.getState().resolvePendingCandidates('user-a');

      const stored = usePostingDraftStore.getState().drafts.find((d) => d.id === draft.id);
      expect(stored?.outcome).toBe('awaiting_place');
      expect(uploadApi.requestUpload).not.toHaveBeenCalled();
    });

    it('marks a draft failed with a clear reason when the candidate was blocked, not attached', async () => {
      (nearbyApi.getCandidateStatus as jest.Mock).mockResolvedValue({
        candidate_id: 'cand-1', resolved: false, place_id: null, blocked: true,
      });

      const draft = await usePostingDraftStore.getState().createDraftFromCapture({
        ownerId: 'user-a',
        sourceUri: 'file:///tmp/photo.jpg',
        kind: 'photo',
        mimeType: 'image/jpeg',
        fileSize: 500_000,
      });
      usePostingDraftStore.getState().setDraftCandidate(draft.id, 'cand-1', 'New Place');

      await usePostingDraftStore.getState().resolvePendingCandidates('user-a');

      const stored = usePostingDraftStore.getState().drafts.find((d) => d.id === draft.id);
      expect(stored?.outcome).toBe('failed');
      expect(stored?.lastError).toContain("wasn't added");
      expect(uploadApi.requestUpload).not.toHaveBeenCalled();
    });

    it('does not check drafts owned by a different (not currently signed-in) user', async () => {
      const draft = await usePostingDraftStore.getState().createDraftFromCapture({
        ownerId: 'user-b',
        sourceUri: 'file:///tmp/photo.jpg',
        kind: 'photo',
        mimeType: 'image/jpeg',
        fileSize: 500_000,
      });
      usePostingDraftStore.getState().setDraftCandidate(draft.id, 'cand-1', 'New Place');

      await usePostingDraftStore.getState().resolvePendingCandidates('user-a');

      expect(nearbyApi.getCandidateStatus).not.toHaveBeenCalled();
    });

    it('does not mark a draft failed on a transient status-check error -- stays awaiting place for next time', async () => {
      (nearbyApi.getCandidateStatus as jest.Mock).mockRejectedValue(new Error('network'));

      const draft = await usePostingDraftStore.getState().createDraftFromCapture({
        ownerId: 'user-a',
        sourceUri: 'file:///tmp/photo.jpg',
        kind: 'photo',
        mimeType: 'image/jpeg',
        fileSize: 500_000,
      });
      usePostingDraftStore.getState().setDraftCandidate(draft.id, 'cand-1', 'New Place');

      await usePostingDraftStore.getState().resolvePendingCandidates('user-a');

      const stored = usePostingDraftStore.getState().drafts.find((d) => d.id === draft.id);
      expect(stored?.outcome).toBe('awaiting_place');
    });

    it('does not check an unresolved (no candidate yet) draft', async () => {
      await usePostingDraftStore.getState().createDraftFromCapture({
        ownerId: 'user-a',
        sourceUri: 'file:///tmp/photo.jpg',
        kind: 'photo',
        mimeType: 'image/jpeg',
        fileSize: 500_000,
      });

      await usePostingDraftStore.getState().resolvePendingCandidates('user-a');

      expect(nearbyApi.getCandidateStatus).not.toHaveBeenCalled();
    });
  });

  it('deleteDraft removes the local file and the draft entry', async () => {
    const draft = await usePostingDraftStore.getState().createDraftFromCapture({
      ownerId: 'user-a',
      sourceUri: 'file:///tmp/photo.jpg',
      kind: 'photo',
      mimeType: 'image/jpeg',
      fileSize: 500_000,
    });

    await usePostingDraftStore.getState().deleteDraft(draft.id);

    expect(FileSystem.deleteAsync).toHaveBeenCalledWith(draft.localUri, { idempotent: true });
    expect(usePostingDraftStore.getState().drafts).toHaveLength(0);
  });
});
