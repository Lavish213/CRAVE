import React from 'react';
import { render } from '@testing-library/react-native';
import FriendsFeedRedirect from '../app/friends-feed';

const mockRedirect = jest.fn((_props: unknown) => null);
jest.mock('expo-router', () => ({ Redirect: (props: unknown) => mockRedirect(props) }));

it('hands legacy friends-feed links to Feed', () => {
  render(<FriendsFeedRedirect />);
  expect(mockRedirect).toHaveBeenCalledWith(expect.objectContaining({ href: '/' }));
});
