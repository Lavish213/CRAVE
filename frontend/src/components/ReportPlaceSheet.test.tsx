// Coverage for the general place-issue report sheet -- the counterpart
// to the photo-only "Report" action Place Detail already had. See
// app/api/v1/routes/moderation.py's place-report endpoints and
// CRAVE_STATUS.md's now-closed "Report is photo-only" gap.
import React from 'react';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
import { ReportPlaceSheet } from './ReportPlaceSheet';
import { reportPlace } from '../api/social';

jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  notificationAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'light' },
  NotificationFeedbackType: { Success: 'success' },
}));
jest.mock('../api/social', () => ({
  reportPlace: jest.fn(),
  PLACE_REPORT_REASONS: [
    { value: 'wrong_hours', label: 'Hours are wrong' },
    { value: 'closed', label: 'This place has closed' },
    { value: 'duplicate', label: 'Duplicate listing' },
    { value: 'wrong_menu', label: 'Menu is wrong or outdated' },
    { value: 'wrong_info', label: 'Other info is wrong' },
    { value: 'other', label: 'Something else' },
  ],
}));

const mockedReportPlace = reportPlace as jest.MockedFunction<typeof reportPlace>;

describe('ReportPlaceSheet', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('reports the selected reason for the given place and calls onReported', async () => {
    mockedReportPlace.mockResolvedValue({ status: 'reported' });
    const onReported = jest.fn();
    const onClose = jest.fn();
    const { getByLabelText } = render(
      <ReportPlaceSheet visible placeId="place-1" onClose={onClose} onReported={onReported} />,
    );

    fireEvent.press(getByLabelText('This place has closed'));

    await waitFor(() => expect(mockedReportPlace).toHaveBeenCalledWith('place-1', 'closed'));
    expect(onReported).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it('still closes and reports success when the server says already_reported', async () => {
    mockedReportPlace.mockResolvedValue({ status: 'already_reported' });
    const onReported = jest.fn();
    const { getByLabelText } = render(
      <ReportPlaceSheet visible placeId="place-1" onClose={jest.fn()} onReported={onReported} />,
    );

    fireEvent.press(getByLabelText('Hours are wrong'));

    await waitFor(() => expect(onReported).toHaveBeenCalled());
  });

  it('shows a sign-in-specific message on a 401', async () => {
    mockedReportPlace.mockRejectedValue({ response: { status: 401 } });
    const { getByLabelText, findByText } = render(
      <ReportPlaceSheet visible placeId="place-1" onClose={jest.fn()} onReported={jest.fn()} />,
    );

    fireEvent.press(getByLabelText('Duplicate listing'));

    expect(await findByText('Sign in to report an issue.')).toBeTruthy();
  });

  it('does nothing without a placeId', () => {
    const { getByLabelText } = render(
      <ReportPlaceSheet visible placeId={null} onClose={jest.fn()} onReported={jest.fn()} />,
    );

    fireEvent.press(getByLabelText('Something else'));

    expect(mockedReportPlace).not.toHaveBeenCalled();
  });
});
