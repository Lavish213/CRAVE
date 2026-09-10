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

jest.mock('../api/videos', () => ({
  requestVideoUpload: jest.fn(),
  uploadVideoToSignedUrl: jest.fn(),
  confirmVideoUpload: jest.fn(),
}));

jest.mock('../api/contributions', () => ({
  createContribution: jest.fn(),
}));

jest.mock('../api/nearby', () => ({
  getCandidateStatus: jest.fn(),
}));

const mockToastShow = jest.fn();
jest.mock('../hooks/useToast', () => ({
  useToast: { getState: () => ({ show: mockToastShow }) },
}));

describe('postingDraftStore final composer lifecycle', () => {
  let usePostingDraftStore: typeof import('./postingDraftStore').usePostingDraftStore;
  let uploadApi: typeof import('../api/upload');
  let videoApi: typeof import('../api/videos');
  let contributionApi: typeof import('../api/contributions');
  let nearbyApi: typeof import('../api/nearby');
  let FileSystem: typeof import('expo-file-system/legacy');

  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
    uploadApi = require('../api/upload');
    videoApi = require('../api/videos');
    contributionApi = require('../api/contributions');
    nearbyApi = require('../api/nearby');
    FileSystem = require('expo-file-system/legacy');
    ({ usePostingDraftStore } = require('./postingDraftStore'));
  });

  it('creates private and social drafts with correct visibility semantics', () => {
    const privateDraft = usePostingDraftStore.getState().createDraft('user-a', 'private_log');
    const socialDraft = usePostingDraftStore.getState().createDraft('user-a', 'social_post');

    expect(privateDraft.visibility).toBe('private');
    expect(privateDraft.localUri).toBeNull();
    expect(privateDraft.restaurantRef).toEqual({ type: 'unresolved' });
    expect(socialDraft.visibility).toBeNull();
    expect(socialDraft.reaction).toBeNull();
  });

  it('persists accepted media locally without touching upload or contribution APIs', async () => {
    const draft = usePostingDraftStore.getState().createDraft('user-a', 'social_post');

    await usePostingDraftStore.getState().addMediaToDraft(draft.id, {
      sourceUri: 'file:///tmp/camera.jpg',
      kind: 'photo',
      mimeType: 'image/jpeg',
      fileSize: 500_000,
    });

    const stored = usePostingDraftStore.getState().drafts.find((item) => item.id === draft.id);
    expect(FileSystem.moveAsync).toHaveBeenCalledTimes(1);
    expect(stored?.localUri).toContain('pending_draft_media/');
    expect(stored?.kind).toBe('photo');
    expect(uploadApi.requestUpload).not.toHaveBeenCalled();
    expect(contributionApi.createContribution).not.toHaveBeenCalled();
  });

  it('selecting an existing restaurant resolves identity without uploading or deleting the draft', () => {
    const draft = usePostingDraftStore.getState().createDraft('user-a', 'private_log');

    usePostingDraftStore.getState().setDraftPlace(draft.id, 'place-1', 'Burma Superstar');

    const stored = usePostingDraftStore.getState().drafts.find((item) => item.id === draft.id);
    expect(stored?.restaurantRef).toEqual({ type: 'place', placeId: 'place-1', displayName: 'Burma Superstar' });
    expect(stored?.outcome).toBe('editing');
    expect(uploadApi.requestUpload).not.toHaveBeenCalled();
    expect(contributionApi.createContribution).not.toHaveBeenCalled();
  });

  it('keeps candidate media intact and resolves candidate to place without uploading', async () => {
    (nearbyApi.getCandidateStatus as jest.Mock).mockResolvedValue({
      candidate_id: 'cand-1',
      resolved: true,
      place_id: 'place-9',
      blocked: false,
    });
    const draft = await usePostingDraftStore.getState().createDraftFromCapture({
      ownerId: 'user-a',
      sourceUri: 'file:///tmp/photo.jpg',
      kind: 'photo',
      mimeType: 'image/jpeg',
      fileSize: 400_000,
    });
    usePostingDraftStore.getState().setDraftCandidate(draft.id, 'cand-1', "Mama Rosa's");

    expect(usePostingDraftStore.getState().drafts.find((item) => item.id === draft.id)?.outcome).toBe('awaiting_place');
    await usePostingDraftStore.getState().resolvePendingCandidates('user-a');

    const stored = usePostingDraftStore.getState().drafts.find((item) => item.id === draft.id);
    expect(stored?.restaurantRef).toEqual({ type: 'place', placeId: 'place-9', displayName: "Mama Rosa's" });
    expect(stored?.localUri).toBe(draft.localUri);
    expect(uploadApi.requestUpload).not.toHaveBeenCalled();
    expect(contributionApi.createContribution).not.toHaveBeenCalled();
  });

  it('returns a blocked candidate to unresolved failure while preserving local media', async () => {
    (nearbyApi.getCandidateStatus as jest.Mock).mockResolvedValue({
      candidate_id: 'cand-1',
      resolved: false,
      place_id: null,
      blocked: true,
    });
    const draft = await usePostingDraftStore.getState().createDraftFromCapture({
      ownerId: 'user-a',
      sourceUri: 'file:///tmp/photo.jpg',
      kind: 'photo',
      mimeType: 'image/jpeg',
      fileSize: 400_000,
    });
    usePostingDraftStore.getState().setDraftCandidate(draft.id, 'cand-1', 'Unconfirmed Place');

    await usePostingDraftStore.getState().resolvePendingCandidates('user-a');

    const stored = usePostingDraftStore.getState().drafts.find((item) => item.id === draft.id);
    expect(stored?.restaurantRef).toEqual({ type: 'unresolved' });
    expect(stored?.outcome).toBe('failed');
    expect(stored?.localUri).toBe(draft.localUri);
    expect(stored?.lastError).toContain("wasn't confirmed");
  });

  it('does not resolve candidate drafts owned by a different account', async () => {
    const draft = usePostingDraftStore.getState().createDraft('user-b', 'private_log');
    usePostingDraftStore.getState().setDraftCandidate(draft.id, 'cand-1', 'New Place');

    await usePostingDraftStore.getState().resolvePendingCandidates('user-a');

    expect(nearbyApi.getCandidateStatus).not.toHaveBeenCalled();
  });

  it('commits a private log without media once a place is selected', async () => {
    (contributionApi.createContribution as jest.Mock).mockResolvedValue({ id: 'contrib-1', status: 'committed' });
    const draft = usePostingDraftStore.getState().createDraft('user-a', 'private_log');
    usePostingDraftStore.getState().setDraftPlace(draft.id, 'place-1', 'Place One');
    usePostingDraftStore.getState().setDraftReaction(draft.id, 'good');

    const result = await usePostingDraftStore.getState().commitDraft(draft.id);

    expect(result?.id).toBe('contrib-1');
    expect(contributionApi.createContribution).toHaveBeenCalledWith(expect.objectContaining({
      client_id: draft.id,
      place_id: 'place-1',
      intent: 'private_log',
      reaction: 'good',
      visibility: 'private',
      image_id: null,
      video_id: null,
    }));
    expect(usePostingDraftStore.getState().drafts.find((item) => item.id === draft.id)).toBeUndefined();
  });

  it('refuses to share without media or without explicit social visibility', async () => {
    const draft = usePostingDraftStore.getState().createDraft('user-a', 'social_post');
    usePostingDraftStore.getState().setDraftPlace(draft.id, 'place-1');

    expect(await usePostingDraftStore.getState().commitDraft(draft.id)).toBeNull();
    expect(contributionApi.createContribution).not.toHaveBeenCalled();

    usePostingDraftStore.getState().setDraftVisibility(draft.id, 'public');
    expect(await usePostingDraftStore.getState().commitDraft(draft.id)).toBeNull();
    expect(contributionApi.createContribution).not.toHaveBeenCalled();
  });

  it('uploads a photo only at explicit commit, then creates contribution and removes local draft', async () => {
    (uploadApi.requestUpload as jest.Mock).mockResolvedValue({ image_id: 'img-1', upload_url: 'https://put.test/image' });
    (uploadApi.uploadToSignedUrl as jest.Mock).mockResolvedValue(undefined);
    (uploadApi.confirmUpload as jest.Mock).mockResolvedValue({ ok: true });
    (contributionApi.createContribution as jest.Mock).mockResolvedValue({ id: 'contrib-1', status: 'committed' });

    const draft = await usePostingDraftStore.getState().createDraftFromCapture({
      ownerId: 'user-a',
      sourceUri: 'file:///tmp/photo.jpg',
      kind: 'photo',
      mimeType: 'image/jpeg',
      fileSize: 500_000,
      intent: 'social_post',
    });
    usePostingDraftStore.getState().setDraftPlace(draft.id, 'place-1');
    usePostingDraftStore.getState().setDraftVisibility(draft.id, 'public');

    const result = await usePostingDraftStore.getState().commitDraft(draft.id);

    expect(result?.id).toBe('contrib-1');
    expect(uploadApi.requestUpload).toHaveBeenCalledWith(expect.objectContaining({ place_id: 'place-1' }));
    expect(uploadApi.confirmUpload).toHaveBeenCalledWith('img-1');
    expect(contributionApi.createContribution).toHaveBeenCalledWith(expect.objectContaining({ image_id: 'img-1', video_id: null }));
    expect(FileSystem.deleteAsync).toHaveBeenCalledWith(expect.stringContaining('pending_draft_media/'), { idempotent: true });
    expect(usePostingDraftStore.getState().drafts.find((item) => item.id === draft.id)).toBeUndefined();
  });

  it('retains uploaded media identity after contribution failure and does not re-upload on retry', async () => {
    (uploadApi.requestUpload as jest.Mock).mockResolvedValue({ image_id: 'img-1', upload_url: 'https://put.test/image' });
    (uploadApi.uploadToSignedUrl as jest.Mock).mockResolvedValue(undefined);
    (uploadApi.confirmUpload as jest.Mock).mockResolvedValue({ ok: true });
    (contributionApi.createContribution as jest.Mock)
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce({ id: 'contrib-1', status: 'committed' });

    const draft = await usePostingDraftStore.getState().createDraftFromCapture({
      ownerId: 'user-a',
      sourceUri: 'file:///tmp/photo.jpg',
      kind: 'photo',
      mimeType: 'image/jpeg',
      fileSize: 500_000,
      intent: 'social_post',
    });
    usePostingDraftStore.getState().setDraftPlace(draft.id, 'place-1');
    usePostingDraftStore.getState().setDraftVisibility(draft.id, 'connections');

    expect(await usePostingDraftStore.getState().commitDraft(draft.id)).toBeNull();
    const failed = usePostingDraftStore.getState().drafts.find((item) => item.id === draft.id);
    expect(failed?.outcome).toBe('failed');
    expect(failed?.uploadedMediaId).toBe('img-1');

    const result = await usePostingDraftStore.getState().commitDraft(draft.id);
    expect(result?.id).toBe('contrib-1');
    expect(uploadApi.requestUpload).toHaveBeenCalledTimes(1);
    expect(contributionApi.createContribution).toHaveBeenCalledTimes(2);
  });

  it('uploads a video at commit and references its server id in the contribution', async () => {
    (videoApi.requestVideoUpload as jest.Mock).mockResolvedValue({ video_id: 'vid-1', upload_url: 'https://put.test/video' });
    (videoApi.uploadVideoToSignedUrl as jest.Mock).mockResolvedValue(undefined);
    (videoApi.confirmVideoUpload as jest.Mock).mockResolvedValue({ ok: true });
    (contributionApi.createContribution as jest.Mock).mockResolvedValue({ id: 'contrib-1', status: 'committed' });

    const draft = await usePostingDraftStore.getState().createDraftFromCapture({
      ownerId: 'user-a',
      sourceUri: 'file:///tmp/clip.mov',
      kind: 'video',
      mimeType: 'video/quicktime',
      fileSize: 2_000_000,
      intent: 'social_post',
    });
    usePostingDraftStore.getState().setDraftPlace(draft.id, 'place-1');
    usePostingDraftStore.getState().setDraftVisibility(draft.id, 'public');

    await usePostingDraftStore.getState().commitDraft(draft.id);

    expect(videoApi.requestVideoUpload).toHaveBeenCalledWith(expect.objectContaining({
      place_id: 'place-1',
      content_type: 'video/quicktime',
      client_id: draft.id,
    }));
    expect(videoApi.confirmVideoUpload).toHaveBeenCalledWith('vid-1');
    expect(contributionApi.createContribution).toHaveBeenCalledWith(expect.objectContaining({ video_id: 'vid-1', image_id: null }));
  });

  it('deleteDraft removes its local media and draft record', async () => {
    const draft = await usePostingDraftStore.getState().createDraftFromCapture({
      ownerId: 'user-a',
      sourceUri: 'file:///tmp/photo.jpg',
      kind: 'photo',
      fileSize: 300_000,
    });

    await usePostingDraftStore.getState().deleteDraft(draft.id);

    expect(FileSystem.deleteAsync).toHaveBeenCalledWith(draft.localUri, { idempotent: true });
    expect(usePostingDraftStore.getState().drafts.find((item) => item.id === draft.id)).toBeUndefined();
  });
});
