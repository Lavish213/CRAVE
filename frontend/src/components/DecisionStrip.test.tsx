import React from 'react';
import { render } from '@testing-library/react-native';
import { DecisionStrip } from './DecisionStrip';

describe('DecisionStrip', () => {
  it('renders canonical Decision Session role copy without fit percentages', () => {
    const { getByText, queryByText } = render(
      <DecisionStrip
        source="decision_session"
        role="best_fit"
        reason="Matches the places you keep choosing."
        fitLabel="Strong fit"
        confidenceLabel="High confidence"
      />,
    );

    expect(getByText('BEST FIT TONIGHT')).toBeTruthy();
    expect(getByText('Strong fit')).toBeTruthy();
    expect(getByText('High confidence')).toBeTruthy();
    expect(queryByText(/%/)).toBeNull();
  });

  it('never fabricates recommendation language for organic entry', () => {
    const { queryByText, getByText } = render(
      <DecisionStrip
        source="organic"
        role="best_fit"
        reason="Should not render"
        fitLabel="Strong fit"
        confidenceLabel="High confidence"
        practicalFacts={{ distance: '1.2 mi', price: '$$' }}
      />,
    );

    expect(queryByText('BEST FIT TONIGHT')).toBeNull();
    expect(queryByText('Should not render')).toBeNull();
    expect(queryByText('Strong fit')).toBeNull();
    expect(queryByText('High confidence')).toBeNull();
    expect(getByText('1.2 mi  ·  $$')).toBeTruthy();
  });

  it('omits missing operational facts instead of inventing them', () => {
    const { getByText, queryByText } = render(
      <DecisionStrip
        source="discovery"
        reason="A different direction that still fits your history."
        practicalFacts={{ distance: '2.1 mi', hours: null }}
      />,
    );

    expect(getByText('WHY CRAVE SURFACED THIS')).toBeTruthy();
    expect(getByText('2.1 mi')).toBeTruthy();
    expect(queryByText(/open/i)).toBeNull();
  });
});
