import {
  assertRecommendationSurface,
  splitRecommendationConstraints,
  type RecommendationContext,
} from './recommendationContext';

describe('recommendationContext', () => {
  it('keeps hard and soft constraints distinct', () => {
    const result = splitRecommendationConstraints([
      { key: 'allergy', value: 'peanut', kind: 'hard', source: 'profile' },
      { key: 'price', value: '$$', kind: 'soft', source: 'filter' },
    ]);

    expect(result.hard_constraints).toEqual([
      { key: 'allergy', value: 'peanut', kind: 'hard', source: 'profile' },
    ]);
    expect(result.soft_constraints).toEqual([
      { key: 'price', value: '$$', kind: 'soft', source: 'filter' },
    ]);
  });

  it('rejects a screen adapter using the wrong recommendation surface', () => {
    const context: RecommendationContext = { surface: 'search' };
    expect(() => assertRecommendationSurface(context, 'decision_session')).toThrow(
      'Expected recommendation surface decision_session, received search.',
    );
  });
});
