// ShareLinkSheet — first dedicated coverage.
//
// This component already had Link and Just-the-name modes wired and
// working; this file locks in the new third mode added alongside the
// hitlist delete/suggest wiring work: "Suggest" (POST /hitlist/suggest —
// name + optional city, no coordinates, no link). Not a full regression
// suite for Link/Just-the-name -- those are already exercised end-to-end
// from craves.test.tsx; this focuses on what's new.
import React from 'react';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
import { ShareLinkSheet } from '../src/components/ShareLinkSheet';
import { suggestPlace } from '../src/api/crave';

jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  notificationAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'light' },
  NotificationFeedbackType: { Success: 'success', Error: 'error' },
}));
jest.mock('../src/hooks/useLocation', () => ({ useLocation: () => null }));
jest.mock('../src/api/crave', () => ({
  detectSourceType: jest.fn(() => 'web'),
  submitPlaceSave: jest.fn(),
  submitShare: jest.fn(),
  suggestPlace: jest.fn(),
}));

const mockedSuggestPlace = suggestPlace as jest.MockedFunction<typeof suggestPlace>;

describe('ShareLinkSheet — Suggest mode', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('shows all three mode toggles and switches into Suggest with name + city fields', () => {
    const { getByLabelText, getByPlaceholderText } = render(
      <ShareLinkSheet visible onClose={jest.fn()} />,
    );

    expect(getByLabelText('Switch to link mode')).toBeTruthy();
    expect(getByLabelText('Switch to just-the-name mode')).toBeTruthy();
    expect(getByLabelText('Switch to suggest mode')).toBeTruthy();

    fireEvent.press(getByLabelText('Switch to suggest mode'));

    expect(getByPlaceholderText('Restaurant name')).toBeTruthy();
    expect(getByPlaceholderText('City (optional)')).toBeTruthy();
  });

  it('submits name + trimmed city hint and reports the "suggest" mode back to the caller', async () => {
    mockedSuggestPlace.mockResolvedValue({
      id: 's1', place_name: 'Nari', source_platform: 'unknown', created_at: null,
    });
    const onSubmitted = jest.fn();
    const onClose = jest.fn();
    const { getByLabelText, getByPlaceholderText } = render(
      <ShareLinkSheet visible onClose={onClose} onSubmitted={onSubmitted} />,
    );

    fireEvent.press(getByLabelText('Switch to suggest mode'));
    fireEvent.changeText(getByPlaceholderText('Restaurant name'), '  Nari  ');
    fireEvent.changeText(getByPlaceholderText('City (optional)'), '  San Francisco  ');
    fireEvent.press(getByLabelText('Submit'));

    await waitFor(() => expect(mockedSuggestPlace).toHaveBeenCalledWith('Nari', 'San Francisco'));
    await waitFor(() => expect(onSubmitted).toHaveBeenCalledWith('suggest'));
    expect(onClose).toHaveBeenCalled();
  });

  it('submits with no city hint at all when the field is left blank', async () => {
    mockedSuggestPlace.mockResolvedValue({
      id: 's2', place_name: 'Nari', source_platform: 'unknown', created_at: null,
    });
    const { getByLabelText, getByPlaceholderText } = render(
      <ShareLinkSheet visible onClose={jest.fn()} />,
    );

    fireEvent.press(getByLabelText('Switch to suggest mode'));
    fireEvent.changeText(getByPlaceholderText('Restaurant name'), 'Nari');
    fireEvent.press(getByLabelText('Submit'));

    await waitFor(() => expect(mockedSuggestPlace).toHaveBeenCalledWith('Nari', undefined));
  });

  it('rejects an empty name without calling suggestPlace', async () => {
    const { getByLabelText, findByText } = render(<ShareLinkSheet visible onClose={jest.fn()} />);

    fireEvent.press(getByLabelText('Switch to suggest mode'));
    fireEvent.press(getByLabelText('Submit'));

    expect(await findByText('Enter the name of the place')).toBeTruthy();
    expect(mockedSuggestPlace).not.toHaveBeenCalled();
  });

  it('shows a sign-in-specific error on a 401', async () => {
    const err: any = new Error('unauthorized');
    err.response = { status: 401 };
    mockedSuggestPlace.mockRejectedValue(err);
    const { getByLabelText, getByPlaceholderText, findByText } = render(
      <ShareLinkSheet visible onClose={jest.fn()} />,
    );

    fireEvent.press(getByLabelText('Switch to suggest mode'));
    fireEvent.changeText(getByPlaceholderText('Restaurant name'), 'Nari');
    fireEvent.press(getByLabelText('Submit'));

    expect(await findByText('Sign in to suggest a place')).toBeTruthy();
  });
});
