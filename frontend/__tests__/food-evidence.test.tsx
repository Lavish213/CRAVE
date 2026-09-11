// app/food-evidence.tsx -- Posting V2 unified composer. Locks in: the
// sign-in gate, the intent-first (private log vs. social post) entry point,
// that media capture persists into the durable draft store immediately
// (never just local component state), that choosing an existing restaurant
// or recording a candidate never uploads/publishes anything by itself, and
// that the composer only calls commitDraft() -- the one place an explicit
// save/post actually happens -- from the final review step.
import React from 'react';
import { act, fireEvent, render } from '@testing-library/react-native';
import { Alert } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import FoodEvidenceScreen from '../app/food-evidence';
import { useAuthStore } from '../src/stores/authStore';
import { searchPlaces } from '../src/api/search';
import type { PostingDraft } from '../src/stores/postingDraftStore';

const mockPush = jest.fn();
const mockBack = jest.fn();
let mockRouteDraftId: string | undefined;
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush, back: mockBack }),
  useLocalSearchParams: () => ({ draftId: mockRouteDraftId }),
}));
jest.mock('expo-image-picker', () => ({
  requestCameraPermissionsAsync: jest.fn(),
  launchCameraAsync: jest.fn(),
  launchImageLibraryAsync: jest.fn(),
}));
jest.mock('../src/stores/authStore', () => ({ useAuthStore: jest.fn() }));
jest.mock('../src/api/search', () => ({ searchPlaces: jest.fn() }));

let mockDrafts: PostingDraft[] = [];
const mockCreateDraft = jest.fn();
const mockAddMediaToDraft = jest.fn();
const mockSetDraftPlace = jest.fn();
const mockSetDraftReaction = jest.fn();
const mockSetDraftCaption = jest.fn();
const mockSetDraftVisibility = jest.fn();
const mockCommitDraft = jest.fn();
const mockDeleteDraft = jest.fn();

function patchDraft(draftId: string, patch: Partial<PostingDraft>) {
  mockDrafts = mockDrafts.map((d) => (d.id === draftId ? { ...d, ...patch } : d));
}

jest.mock('../src/stores/postingDraftStore', () => {
  const actual = jest.requireActual('../src/stores/postingDraftStore');
  return {
    ...actual,
    usePostingDraftStore: (selector: (s: Record<string, unknown>) => unknown) =>
      selector({
        get drafts() {
          return mockDrafts;
        },
        createDraft: mockCreateDraft,
        addMediaToDraft: mockAddMediaToDraft,
        setDraftPlace: mockSetDraftPlace,
        setDraftReaction: mockSetDraftReaction,
        setDraftCaption: mockSetDraftCaption,
        setDraftVisibility: mockSetDraftVisibility,
        commitDraft: mockCommitDraft,
        deleteDraft: mockDeleteDraft,
      }),
  };
});

const mockToastShow = jest.fn();
jest.mock('../src/hooks/useToast', () => ({
  useToast: (selector: (s: { show: (msg: string) => void }) => unknown) => selector({ show: mockToastShow }),
}));
jest.mock('../src/components/AuthSheet', () => {
  const { Text } = require('react-native');
  return { AuthSheet: ({ visible }: { visible: boolean }) => (visible ? <Text testID="auth-sheet-visible">auth</Text> : null) };
});

const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;
const mockedRequestCameraPermission = ImagePicker.requestCameraPermissionsAsync as jest.Mock;
const mockedLaunchCamera = ImagePicker.launchCameraAsync as jest.Mock;
const mockedLaunchLibrary = ImagePicker.launchImageLibraryAsync as jest.Mock;
const mockedSearchPlaces = searchPlaces as jest.MockedFunction<typeof searchPlaces>;

function setAuth(user: { id: string } | null) {
  mockedUseAuthStore.mockImplementation((selector: (s: unknown) => unknown) => selector({ user }));
}

function makeDraft(overrides: Partial<PostingDraft> = {}): PostingDraft {
  const now = Date.now();
  return {
    id: 'draft-1',
    ownerId: 'user-1',
    localUri: null,
    kind: null,
    uploadedMediaId: null,
    restaurantRef: { type: 'unresolved' },
    intent: 'private_log',
    reaction: null,
    caption: '',
    visibility: null,
    occurredAt: null,
    outcome: 'editing',
    lastError: null,
    createdAt: now,
    updatedAt: now,
    ...overrides,
  };
}

describe('FoodEvidenceScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockRouteDraftId = undefined;
    mockDrafts = [];
    setAuth({ id: 'user-1' });

    mockCreateDraft.mockImplementation((ownerId: string, intent: 'private_log' | 'social_post') => {
      const draft = makeDraft({ id: 'new-draft', ownerId, intent });
      mockDrafts = [draft, ...mockDrafts];
      return draft;
    });
    mockAddMediaToDraft.mockImplementation(async (draftId: string, opts: { sourceUri: string; kind: 'photo' | 'video'; mimeType?: string; fileSize?: number }) => {
      patchDraft(draftId, { localUri: `file:///durable/${draftId}.jpg`, kind: opts.kind, mimeType: opts.mimeType, fileSize: opts.fileSize });
    });
    mockSetDraftPlace.mockImplementation((draftId: string, placeId: string, displayName?: string) => {
      patchDraft(draftId, { restaurantRef: { type: 'place', placeId, displayName } });
    });
    mockSetDraftReaction.mockImplementation((draftId: string, reaction: PostingDraft['reaction']) => {
      patchDraft(draftId, { reaction });
    });
    mockSetDraftCaption.mockImplementation((draftId: string, caption: string) => {
      patchDraft(draftId, { caption });
    });
    mockSetDraftVisibility.mockImplementation((draftId: string, visibility: PostingDraft['visibility']) => {
      patchDraft(draftId, { visibility });
    });
    mockCommitDraft.mockResolvedValue({ id: 'contribution-1' });
    mockDeleteDraft.mockImplementation(async (draftId: string) => {
      mockDrafts = mockDrafts.filter((d) => d.id !== draftId);
    });
  });

  it('shows a sign-in gate and never creates a draft when signed out', async () => {
    setAuth(null);
    const { findByText, findByTestId, queryByText } = render(<FoodEvidenceScreen />);
    expect(await findByText('Sign in before CRAVE saves a private log or post to your account.')).toBeTruthy();
    expect(queryByText('Log what I ate')).toBeNull();

    fireEvent.press(await findByText('Sign in'));
    expect(await findByTestId('auth-sheet-visible')).toBeTruthy();
    expect(mockCreateDraft).not.toHaveBeenCalled();
  });

  it('starts a private-log draft and lets media be skipped entirely', async () => {
    const { findByText } = render(<FoodEvidenceScreen />);
    fireEvent.press(await findByText('Log what I ate'));
    expect(mockCreateDraft).toHaveBeenCalledWith('user-1', 'private_log');

    expect(await findByText('Add the food')).toBeTruthy();
    fireEvent.press(await findByText('Skip media'));
    expect(await findByText('Where was this?')).toBeTruthy();
  });

  it('does not offer to skip media for a social post -- media is required', async () => {
    const { findByText, queryByText } = render(<FoodEvidenceScreen />);
    fireEvent.press(await findByText('Share a food find'));
    expect(mockCreateDraft).toHaveBeenCalledWith('user-1', 'social_post');
    expect(await findByText('Add the food')).toBeTruthy();
    expect(queryByText('Skip media')).toBeNull();
  });

  it('persists a camera photo into the draft store and advances to preview', async () => {
    mockedRequestCameraPermission.mockResolvedValue({ granted: true });
    mockedLaunchCamera.mockResolvedValue({
      canceled: false,
      assets: [{ uri: 'file://photo.jpg', fileSize: 500000, mimeType: 'image/jpeg' }],
    });

    const { findByText } = render(<FoodEvidenceScreen />);
    fireEvent.press(await findByText('Log what I ate'));
    await act(async () => {
      fireEvent.press(await findByText('Take photo'));
    });

    expect(mockAddMediaToDraft).toHaveBeenCalledWith('new-draft', {
      sourceUri: 'file://photo.jpg',
      kind: 'photo',
      mimeType: 'image/jpeg',
      fileSize: 500000,
    });
    expect(await findByText('Keep this?')).toBeTruthy();
    fireEvent.press(await findByText('Use photo'));
    expect(await findByText('Where was this?')).toBeTruthy();
  });

  it('warns instead of opening the camera when camera permission is denied', async () => {
    mockedRequestCameraPermission.mockResolvedValue({ granted: false });
    const alertSpy = jest.spyOn(Alert, 'alert').mockImplementation(() => {});

    const { findByText } = render(<FoodEvidenceScreen />);
    fireEvent.press(await findByText('Log what I ate'));
    await act(async () => {
      fireEvent.press(await findByText('Take photo'));
    });

    expect(mockedLaunchCamera).not.toHaveBeenCalled();
    expect(mockAddMediaToDraft).not.toHaveBeenCalled();
    expect(alertSpy).toHaveBeenCalledWith('Camera unavailable', expect.any(String));
    alertSpy.mockRestore();
  });

  it('persists a library-picked video and shows the video preview branch', async () => {
    mockedLaunchLibrary.mockResolvedValue({
      canceled: false,
      assets: [{ uri: 'file://clip.mov', type: 'video' }],
    });

    const { findByText } = render(<FoodEvidenceScreen />);
    fireEvent.press(await findByText('Share a food find'));
    await act(async () => {
      fireEvent.press(await findByText('Choose from library'));
    });

    expect(mockAddMediaToDraft).toHaveBeenCalledWith('new-draft', expect.objectContaining({ kind: 'video', sourceUri: 'file://clip.mov' }));
    expect(await findByText('Video saved')).toBeTruthy();
    fireEvent.press(await findByText('Use video'));
    expect(await findByText('Where was this?')).toBeTruthy();
  });

  it('toasts instead of crashing when persisting captured media fails', async () => {
    mockedLaunchLibrary.mockResolvedValue({ canceled: false, assets: [{ uri: 'file://photo.jpg' }] });
    mockAddMediaToDraft.mockRejectedValueOnce(new Error("Couldn't save that media"));

    const { findByText } = render(<FoodEvidenceScreen />);
    fireEvent.press(await findByText('Log what I ate'));
    await act(async () => {
      fireEvent.press(await findByText('Choose from library'));
    });

    expect(mockToastShow).toHaveBeenCalledWith("Couldn't save that media");
  });

  it('searches restaurants by name and selecting one only identifies the draft, never uploads', async () => {
    mockedSearchPlaces.mockResolvedValue({
      items: [{ id: 'place-1', name: 'Tasty Spot', address: '1 Main St' }],
    } as never);

    const { findByText, findByLabelText } = render(<FoodEvidenceScreen />);
    fireEvent.press(await findByText('Log what I ate'));
    fireEvent.press(await findByText('Skip media'));

    const input = await findByLabelText('Search restaurant name');
    fireEvent.changeText(input, 'Tasty');
    await act(async () => {
      fireEvent(input, 'submitEditing');
    });

    fireEvent.press(await findByText('Tasty Spot'));
    expect(mockSetDraftPlace).toHaveBeenCalledWith('new-draft', 'place-1', 'Tasty Spot');
    expect(await findByText('How was it?')).toBeTruthy();
  });

  it('does not lose the draft when a search query is too short -- prompts instead of calling the API', async () => {
    const { findByText, findByLabelText } = render(<FoodEvidenceScreen />);
    fireEvent.press(await findByText('Log what I ate'));
    fireEvent.press(await findByText('Skip media'));

    const input = await findByLabelText('Search restaurant name');
    fireEvent.changeText(input, 'a');
    await act(async () => {
      fireEvent(input, 'submitEditing');
    });

    expect(mockedSearchPlaces).not.toHaveBeenCalled();
    expect(mockToastShow).toHaveBeenCalledWith('Type at least two letters to search restaurants.');
  });

  it('routes to add-spot with the draft id when the restaurant cannot be found', async () => {
    const { findByText } = render(<FoodEvidenceScreen />);
    fireEvent.press(await findByText('Log what I ate'));
    fireEvent.press(await findByText('Skip media'));

    fireEvent.press(await findByText("Can't find it? Add this place"));
    expect(mockPush).toHaveBeenCalledWith({ pathname: '/add-spot', params: { draftId: 'new-draft' } });
  });

  it('shows the pending-candidate banner and a "finish later" exit once a candidate is attached', async () => {
    mockRouteDraftId = 'draft-pending';
    mockDrafts = [makeDraft({ id: 'draft-pending', restaurantRef: { type: 'candidate', candidateId: 'cand-1', displayName: 'New Spot' } })];

    const { findByText } = render(<FoodEvidenceScreen />);
    expect(await findByText("We're verifying this restaurant. Your draft and media stay saved.")).toBeTruthy();

    fireEvent.press(await findByText('Finish later'));
    expect(mockBack).toHaveBeenCalled();
  });

  async function pickExistingPlace(findByText: (text: string) => Promise<unknown>, findByLabelText: (label: string) => Promise<unknown>) {
    mockedSearchPlaces.mockResolvedValue({
      items: [{ id: 'place-1', name: 'Existing Place', address: '1 Main St' }],
    } as never);
    const input = await findByLabelText('Search restaurant name');
    fireEvent.changeText(input as never, 'Existing');
    await act(async () => {
      fireEvent(input as never, 'submitEditing');
    });
    fireEvent.press((await findByText('Existing Place')) as never);
  }

  it('walks reaction -> caption -> review for a private log, skipping the visibility step entirely', async () => {
    const { findByText, findByLabelText, findAllByText, queryByText } = render(<FoodEvidenceScreen />);
    fireEvent.press(await findByText('Log what I ate'));
    fireEvent.press(await findByText('Skip media'));
    await pickExistingPlace(findByText, findByLabelText);
    expect(mockSetDraftPlace).toHaveBeenCalledWith('new-draft', 'place-1', 'Existing Place');

    fireEvent.press(await findByText('Loved it'));
    expect(mockSetDraftReaction).toHaveBeenCalledWith('new-draft', 'loved');

    const note = await findByLabelText('Optional note about the meal');
    fireEvent.changeText(note, 'Great ramen');
    fireEvent.press(await findByText('Continue'));

    expect(mockSetDraftCaption).toHaveBeenCalledWith('new-draft', 'Great ramen');
    expect(queryByText('Who can see this?')).toBeNull();
    // "Save privately" is both the review step's heading and its commit
    // button label for a private log -- findByText would be ambiguous.
    expect((await findAllByText('Save privately')).length).toBe(2);
  });

  it('requires an explicit audience for a social post before reaching review', async () => {
    const { findByText, findByLabelText } = render(<FoodEvidenceScreen />);
    fireEvent.press(await findByText('Share a food find'));
    mockedLaunchLibrary.mockResolvedValue({ canceled: false, assets: [{ uri: 'file://photo.jpg' }] });
    await act(async () => {
      fireEvent.press(await findByText('Choose from library'));
    });
    fireEvent.press(await findByText('Use photo'));
    await pickExistingPlace(findByText, findByLabelText);
    fireEvent.press(await findByText('Skip'));
    fireEvent.press(await findByText('Skip note'));

    expect(await findByText('Who can see this?')).toBeTruthy();
    fireEvent.press(await findByText('Public'));
    expect(mockSetDraftVisibility).toHaveBeenCalledWith('new-draft', 'public');
    expect(await findByText('Post publicly')).toBeTruthy();
  });

  it('commits the draft on review and goes back on success', async () => {
    const { findByText, findByLabelText, findAllByText } = render(<FoodEvidenceScreen />);
    fireEvent.press(await findByText('Log what I ate'));
    fireEvent.press(await findByText('Skip media'));
    await pickExistingPlace(findByText, findByLabelText);
    fireEvent.press(await findByText('Skip'));
    fireEvent.press(await findByText('Skip note'));

    await act(async () => {
      // Index 1: "Save privately" is both the review heading and the
      // commit button's label for a private log -- the button is second.
      const [, commitButton] = await findAllByText('Save privately');
      fireEvent.press(commitButton);
    });

    expect(mockCommitDraft).toHaveBeenCalledWith('new-draft');
    expect(mockBack).toHaveBeenCalled();
  });

  it('keeps the draft and does not navigate away when committing fails', async () => {
    mockCommitDraft.mockResolvedValueOnce(null);
    const { findByText, findByLabelText, findAllByText } = render(<FoodEvidenceScreen />);
    fireEvent.press(await findByText('Log what I ate'));
    fireEvent.press(await findByText('Skip media'));
    await pickExistingPlace(findByText, findByLabelText);
    fireEvent.press(await findByText('Skip'));
    fireEvent.press(await findByText('Skip note'));

    await act(async () => {
      const [, commitButton] = await findAllByText('Save privately');
      fireEvent.press(commitButton);
    });

    expect(mockCommitDraft).toHaveBeenCalledWith('new-draft');
    expect(mockBack).not.toHaveBeenCalled();
    expect((await findAllByText('Save privately')).length).toBe(2);
  });

  it('deletes the draft and returns to the intent step', async () => {
    const { findByText, findByLabelText } = render(<FoodEvidenceScreen />);
    fireEvent.press(await findByText('Log what I ate'));

    await act(async () => {
      fireEvent.press(await findByLabelText('Delete draft'));
    });

    expect(mockDeleteDraft).toHaveBeenCalledWith('new-draft');
    expect(await findByText('What are you doing?')).toBeTruthy();
  });

  it('resumes an existing draft at the correct step when opened with a draftId param', async () => {
    mockRouteDraftId = 'draft-resume';
    mockDrafts = [
      makeDraft({
        id: 'draft-resume',
        localUri: 'file:///durable/draft-resume.jpg',
        kind: 'photo',
        restaurantRef: { type: 'place', placeId: 'place-9', displayName: 'Resumed Place' },
      }),
    ];

    const { findByText } = render(<FoodEvidenceScreen />);
    expect(await findByText('How was it?')).toBeTruthy();
  });

  it('auto-resumes the most recent owned draft on mount instead of showing the intent screen again', async () => {
    mockDrafts = [
      makeDraft({
        id: 'draft-a',
        intent: 'social_post',
        localUri: 'file:///durable/draft-a.jpg',
        kind: 'photo',
        restaurantRef: { type: 'candidate', candidateId: 'c1', displayName: 'Maybe Place' },
      }),
    ];

    const { findByText, queryByText } = render(<FoodEvidenceScreen />);
    expect(await findByText("We're verifying this restaurant. Your draft and media stay saved.")).toBeTruthy();
    expect(queryByText('What are you doing?')).toBeNull();
  });

  it('shows the resumable-drafts list on the intent screen once the active draft is discarded, and reopens a listed one at its own recovery step', async () => {
    mockDrafts = [
      makeDraft({ id: 'draft-active', createdAt: 2, updatedAt: 2 }),
      makeDraft({ id: 'draft-b', createdAt: 1, updatedAt: 1, restaurantRef: { type: 'candidate', candidateId: 'c1', displayName: 'Maybe Place' } }),
    ];

    const { findByText, findByLabelText } = render(<FoodEvidenceScreen />);
    // draft-active is ownedDrafts[0] and is auto-resumed; discarding it should
    // fall back to the intent screen, which now has a real second draft to list.
    await act(async () => {
      fireEvent.press(await findByLabelText('Delete draft'));
    });
    expect(mockDeleteDraft).toHaveBeenCalledWith('draft-active');

    expect(await findByText('YOUR DRAFTS')).toBeTruthy();
    expect(await findByText('Maybe Place')).toBeTruthy();

    fireEvent.press(await findByText('Maybe Place'));
    expect(await findByText('Where was this?')).toBeTruthy();
  });
});
