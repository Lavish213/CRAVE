import React from 'react';
import { fireEvent, render } from '@testing-library/react-native';
import { AuthSheet } from './AuthSheet';

const mockPush = jest.fn();
jest.mock('expo-router', () => ({ useRouter: () => ({ push: mockPush }) }));
jest.mock('expo-web-browser', () => ({
  maybeCompleteAuthSession: jest.fn(),
  openAuthSessionAsync: jest.fn(),
}));
jest.mock('expo-auth-session', () => ({ makeRedirectUri: jest.fn(() => 'crave://auth') }));
jest.mock('expo-auth-session/build/QueryParams', () => ({ getQueryParams: jest.fn(() => ({ params: {} })) }));
jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  ImpactFeedbackStyle: { Medium: 'medium' },
}));
jest.mock('../lib/supabase', () => ({
  supabase: { auth: { signInWithOAuth: jest.fn(), setSession: jest.fn() } },
}));

it('opens the real Terms and Privacy routes and closes the sheet', () => {
  const onClose = jest.fn();
  const { getByLabelText } = render(<AuthSheet visible onClose={onClose} />);

  fireEvent.press(getByLabelText('Terms of Service'));
  expect(onClose).toHaveBeenCalledTimes(1);
  expect(mockPush).toHaveBeenCalledWith('/legal/terms');

  fireEvent.press(getByLabelText('Privacy Policy'));
  expect(onClose).toHaveBeenCalledTimes(2);
  expect(mockPush).toHaveBeenCalledWith('/legal/privacy');
});
