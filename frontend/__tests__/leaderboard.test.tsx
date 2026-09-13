import React from 'react';
import { render } from '@testing-library/react-native';
import LeaderboardRedirect from '../app/leaderboard';

const mockRedirect = jest.fn((_props: unknown) => null);
jest.mock('expo-router', () => ({ Redirect: (props: unknown) => mockRedirect(props) }));

it('hands legacy leaderboard links to Profile', () => {
  render(<LeaderboardRedirect />);
  expect(mockRedirect).toHaveBeenCalledWith(expect.objectContaining({ href: '/profile' }));
});
