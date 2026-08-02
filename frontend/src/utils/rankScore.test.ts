import {
  RECOMMENDATION_THRESHOLD,
  TIER_CHOICES,
  TIER_LABELS,
  estimateComparisons,
  formatScore,
  rankedListHeadline,
  recommendationProgress,
  tierColor,
} from './rankScore';
import { Colors } from '../constants/colors';

describe('formatScore', () => {
  it('renders one decimal place', () => {
    expect(formatScore(8)).toBe('8.0');
    expect(formatScore(7.25)).toBe('7.3');
    expect(formatScore(10)).toBe('10.0');
    expect(formatScore(0)).toBe('0.0');
  });
});

describe('tierColor', () => {
  it('gives each tier a distinct colour', () => {
    const colors = [tierColor('liked'), tierColor('fine'), tierColor('disliked')];
    expect(new Set(colors).size).toBe(3);
  });

  it('uses the shared palette rather than ad-hoc hex', () => {
    expect(tierColor('liked')).toBe(Colors.success);
    expect(tierColor('fine')).toBe(Colors.warning);
  });
});

describe('tier metadata', () => {
  it('offers exactly the three backend tiers, best first', () => {
    expect(TIER_CHOICES.map((c) => c.tier)).toEqual(['liked', 'fine', 'disliked']);
  });

  it('labels every tier it offers', () => {
    for (const choice of TIER_CHOICES) {
      expect(TIER_LABELS[choice.tier]).toBeTruthy();
    }
  });
});

describe('estimateComparisons', () => {
  it('is zero for an empty list — nothing to compare against', () => {
    expect(estimateComparisons(0)).toBe(0);
  });

  it('grows logarithmically, not linearly', () => {
    // Binary insertion: doubling the list adds one comparison, which is the
    // whole reason the flow stays short as someone ranks hundreds of places.
    expect(estimateComparisons(1)).toBe(1);
    expect(estimateComparisons(3)).toBe(2);
    expect(estimateComparisons(7)).toBe(3);
    expect(estimateComparisons(255)).toBe(8);
  });

  it('never returns zero for a non-empty list', () => {
    for (let n = 1; n <= 50; n++) {
      expect(estimateComparisons(n)).toBeGreaterThanOrEqual(1);
    }
  });
});

describe('rankedListHeadline', () => {
  it('never renders a bare count', () => {
    // The Spotify-Wrapped lesson: the headline is a statement about the
    // person, so it must always carry words, not just a number.
    for (const n of [0, 1, 3, 10, 30, 200]) {
      const headline = rankedListHeadline(n);
      expect(headline).toBeTruthy();
      expect(headline).not.toMatch(/^\d+$/);
      expect(headline.length).toBeGreaterThan(10);
    }
  });

  it('handles the empty and singular cases without saying "0 places"', () => {
    expect(rankedListHeadline(0)).not.toContain('0 places');
    expect(rankedListHeadline(1)).not.toContain('1 places');
  });

  it('includes the count once there is one worth showing', () => {
    expect(rankedListHeadline(42)).toContain('42');
  });
});

describe('recommendationProgress', () => {
  it('stays locked below the threshold and reports what is left', () => {
    const { unlocked, remaining } = recommendationProgress(10);
    expect(unlocked).toBe(false);
    expect(remaining).toBe(RECOMMENDATION_THRESHOLD - 10);
  });

  it('unlocks exactly at the threshold', () => {
    expect(recommendationProgress(RECOMMENDATION_THRESHOLD).unlocked).toBe(true);
    expect(recommendationProgress(RECOMMENDATION_THRESHOLD - 1).unlocked).toBe(false);
  });

  it('never reports negative remaining once past the threshold', () => {
    const { unlocked, remaining } = recommendationProgress(999);
    expect(unlocked).toBe(true);
    expect(remaining).toBe(0);
  });
});
