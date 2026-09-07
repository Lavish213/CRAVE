import { isRankEligibleVisitEvidence, visitEvidenceImpliesPreference } from './evidence';

describe('visit evidence rules', () => {
  it.each([
    ['declared', true],
    ['verified', true],
    ['inferred', false],
  ] as const)('%s visit evidence rank eligibility is %s', (tier, expected) => {
    expect(isRankEligibleVisitEvidence({ tier, deletedAt: null })).toBe(expected);
  });

  it('deleted evidence never unlocks Rank', () => {
    expect(isRankEligibleVisitEvidence({ tier: 'verified', deletedAt: '2026-09-07T00:00:00Z' })).toBe(false);
  });

  it('never treats a visit itself as preference evidence', () => {
    expect(visitEvidenceImpliesPreference()).toBe(false);
  });
});
