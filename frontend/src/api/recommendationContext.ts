export type RecommendationSurface =
  | 'decision_session'
  | 'discovery'
  | 'craves'
  | 'search'
  | 'map'
  | 'map_direct';

export type RecommendationConstraintKind = 'hard' | 'soft';
export type RecommendationConstraintSource =
  | 'explicit_query'
  | 'filter'
  | 'profile'
  | 'session';

export interface RecommendationConstraint {
  key: string;
  value: string;
  kind: RecommendationConstraintKind;
  source: RecommendationConstraintSource;
}

export interface RecommendationLocationContext {
  city_id?: string;
  lat?: number;
  lng?: number;
  radius_miles?: number;
}

export interface RecommendationContext {
  surface: RecommendationSurface;
  location?: RecommendationLocationContext;
  time_context?: string;
  query?: string;
  hard_constraints?: RecommendationConstraint[];
  soft_constraints?: RecommendationConstraint[];
  novelty?: 'familiar' | 'balanced' | 'adventurous';
  candidate_scope?: 'all' | 'craves';
  session_id?: string;
  cursor?: string;
}

export function splitRecommendationConstraints(
  constraints: readonly RecommendationConstraint[],
): Pick<RecommendationContext, 'hard_constraints' | 'soft_constraints'> {
  return {
    hard_constraints: constraints.filter((constraint) => constraint.kind === 'hard'),
    soft_constraints: constraints.filter((constraint) => constraint.kind === 'soft'),
  };
}

export function assertRecommendationSurface(
  context: RecommendationContext,
  expected: RecommendationSurface,
): void {
  if (context.surface !== expected) {
    throw new Error(`Expected recommendation surface ${expected}, received ${context.surface}.`);
  }
}
