export type VisitEvidenceTier = 'declared' | 'verified' | 'inferred';

export interface VisitEvidenceRef {
  placeId: string;
  tier: VisitEvidenceTier;
  source: string;
  occurredAt?: string | null;
  correctedAt?: string | null;
  deletedAt?: string | null;
}

/** Rank eligibility requires user-declared or independently verified experience. */
export function isRankEligibleVisitEvidence(
  evidence: Pick<VisitEvidenceRef, 'tier' | 'deletedAt'>,
): boolean {
  if (evidence.deletedAt) return false;
  return evidence.tier === 'declared' || evidence.tier === 'verified';
}

/** A visit establishes experience only. Preference must come from a separate signal. */
export function visitEvidenceImpliesPreference(): false {
  return false;
}
