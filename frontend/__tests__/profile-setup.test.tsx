// profile-setup.tsx — first dedicated coverage. Locks in: the
// idle/invalid/checking/available/taken availability state machine
// (with its real 400ms debounce, not mocked away -- same convention as
// search.test.tsx's own debounced-query test), the out-of-order
// response guard (latestQuery), submit gating on availability, and both
// submit outcomes.
import React from 'react';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
import ProfileSetupScreen from '../app/profile-setup';
import { checkUsernameAvailable, setupProfile } from '../src/api/social';

const mockReplace = jest.fn();
jest.mock('expo-router', () => ({
  useRouter: () => ({ replace: mockReplace }),
}));
jest.mock('../src/api/social', () => ({
  checkUsernameAvailable: jest.fn(),
  setupProfile: jest.fn(),
}));
jest.mock('expo-haptics', () => ({
  notificationAsync: jest.fn(),
  NotificationFeedbackType: { Success: 'success' },
}));

const mockedCheckUsernameAvailable = checkUsernameAvailable as jest.MockedFunction<typeof checkUsernameAvailable>;
const mockedSetupProfile = setupProfile as jest.MockedFunction<typeof setupProfile>;

describe('ProfileSetupScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('starts idle with submit disabled, and never calls the availability check for an empty username', () => {
    const { getByText, getByLabelText } = render(<ProfileSetupScreen />);
    expect(getByText('Letters, numbers and underscores. 3-20 characters.')).toBeTruthy();
    expect(getByLabelText('Continue').props.accessibilityState?.disabled).not.toBe(false);
    expect(mockedCheckUsernameAvailable).not.toHaveBeenCalled();
  });

  it('shows invalid immediately for a bad username, without ever checking availability', () => {
    const { getByLabelText, getByText } = render(<ProfileSetupScreen />);
    fireEvent.changeText(getByLabelText('Username'), 'a b');

    expect(getByText('Letters, numbers and underscores only, 3-20 characters.')).toBeTruthy();
    expect(mockedCheckUsernameAvailable).not.toHaveBeenCalled();
  });

  it('debounces a valid username through checking to available, and enables submit', async () => {
    mockedCheckUsernameAvailable.mockResolvedValue(true);
    const { getByLabelText, findByText, getByText } = render(<ProfileSetupScreen />);

    fireEvent.changeText(getByLabelText('Username'), 'newhandle');
    expect(getByText('Checking…')).toBeTruthy();

    expect(await findByText('Available')).toBeTruthy();
    expect(mockedCheckUsernameAvailable).toHaveBeenCalledWith('newhandle');
    expect(getByLabelText('Continue').props.accessibilityState?.disabled).toBeFalsy();
  });

  it('shows taken for an unavailable username, with submit staying disabled', async () => {
    mockedCheckUsernameAvailable.mockResolvedValue(false);
    const { getByLabelText, findByText } = render(<ProfileSetupScreen />);

    fireEvent.changeText(getByLabelText('Username'), 'alreadytaken');
    expect(await findByText('Already taken')).toBeTruthy();
    expect(getByLabelText('Continue').props.accessibilityState?.disabled).toBe(true);
  });

  it('surfaces a real error (not idle) when the availability check itself fails, with a working retry', async () => {
    // Confirmed real bug: a failed check previously collapsed to 'idle',
    // indistinguishable from "haven't typed a valid username yet," with
    // no retry path -- retyping the exact same text never reruns the
    // debounce effect (its dependency is the text itself, unchanged
    // value means no re-render).
    mockedCheckUsernameAvailable.mockRejectedValueOnce(new Error('network'));
    const { getByLabelText, findByText, queryByText } = render(<ProfileSetupScreen />);

    fireEvent.changeText(getByLabelText('Username'), 'newhandle');
    expect(await findByText("Couldn't check availability — tap to retry.")).toBeTruthy();
    expect(queryByText('Letters, numbers and underscores. 3-20 characters.')).toBeNull();
    expect(getByLabelText('Continue').props.accessibilityState?.disabled).toBe(true);

    mockedCheckUsernameAvailable.mockResolvedValueOnce(true);
    fireEvent.press(getByLabelText('Retry checking username availability'));

    expect(await findByText('Available')).toBeTruthy();
    expect(mockedCheckUsernameAvailable).toHaveBeenCalledTimes(2);
  });

  it('does not let a slower, earlier check overwrite a later, faster one', async () => {
    let resolveSlow: (ok: boolean) => void;
    mockedCheckUsernameAvailable.mockImplementationOnce(
      () => new Promise((resolve) => { resolveSlow = resolve; }),
    );
    const { getByLabelText, findByText } = render(<ProfileSetupScreen />);

    fireEvent.changeText(getByLabelText('Username'), 'firstslow');
    await waitFor(() => expect(mockedCheckUsernameAvailable).toHaveBeenCalledWith('firstslow'), { timeout: 2000 });

    mockedCheckUsernameAvailable.mockResolvedValueOnce(false);
    fireEvent.changeText(getByLabelText('Username'), 'secondfast');
    expect(await findByText('Already taken')).toBeTruthy();

    // The first (slow) query's response now lands late -- it must not
    // overwrite the correct "Already taken" state for the current query.
    await act(async () => {
      resolveSlow!(true);
    });
    expect(await findByText('Already taken')).toBeTruthy();
  });

  it('submits with the normalized username and trimmed display name, then navigates to profile', async () => {
    mockedCheckUsernameAvailable.mockResolvedValue(true);
    mockedSetupProfile.mockResolvedValue({ id: 'me', username: 'newhandle', display_name: null, avatar_url: null, bio: null, is_public: true });

    const { getByLabelText, findByText } = render(<ProfileSetupScreen />);
    fireEvent.changeText(getByLabelText('Username'), '  NewHandle  ');
    fireEvent.changeText(getByLabelText('Display name'), '  My Name  ');
    await findByText('Available');

    await act(async () => {
      fireEvent.press(getByLabelText('Continue'));
    });

    expect(mockedSetupProfile).toHaveBeenCalledWith('newhandle', 'My Name');
    expect(mockReplace).toHaveBeenCalledWith('/profile');
  });

  it('sends undefined for an empty display name', async () => {
    mockedCheckUsernameAvailable.mockResolvedValue(true);
    mockedSetupProfile.mockResolvedValue({ id: 'me', username: 'newhandle', display_name: null, avatar_url: null, bio: null, is_public: true });

    const { getByLabelText, findByText } = render(<ProfileSetupScreen />);
    fireEvent.changeText(getByLabelText('Username'), 'newhandle');
    await findByText('Available');

    await act(async () => {
      fireEvent.press(getByLabelText('Continue'));
    });

    expect(mockedSetupProfile).toHaveBeenCalledWith('newhandle', undefined);
  });

  it('shows the server error message on a failed submit, and does not navigate away', async () => {
    mockedCheckUsernameAvailable.mockResolvedValue(true);
    mockedSetupProfile.mockRejectedValue({ response: { data: { detail: 'Username was just claimed by someone else' } } });

    const { getByLabelText, findByText } = render(<ProfileSetupScreen />);
    fireEvent.changeText(getByLabelText('Username'), 'newhandle');
    await findByText('Available');

    await act(async () => {
      fireEvent.press(getByLabelText('Continue'));
    });

    expect(await findByText('Username was just claimed by someone else')).toBeTruthy();
    expect(mockReplace).not.toHaveBeenCalled();
  });
});
