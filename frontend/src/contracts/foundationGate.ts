/**
 * Foundation Gate contracts.
 *
 * These types intentionally lock interfaces and invariants only. They do not
 * force every route to migrate at once; slices import them when they touch a
 * screen and then prove the pattern in that screen.
 */

export type ErrorKind =
  | 'offline'
  | 'timeout'
  | 'unauthorized'
  | 'forbidden'
  | 'not_found'
  | 'rate_limited'
  | 'server_error'
  | 'invalid_data'
  | 'cancelled'
  | 'unknown';

export type ErrorRecoverability =
  | 'retry_now'
  | 'retry_later'
  | 'sign_in'
  | 'request_access'
  | 'change_input'
  | 'no_action';

export type ErrorVisibility =
  | 'silent_telemetry'
  | 'inline'
  | 'toast'
  | 'full_state'
  | 'auth_gate';

export interface ErrorPresentation {
  kind: ErrorKind;
  recoverability: ErrorRecoverability;
  visibility: ErrorVisibility;
  title: string;
  message: string;
  retryable: boolean;
  preservesUserInput: boolean;
}

export type ErrorSwallowClass =
  | 'ignorable_cleanup'
  | 'recoverable_background'
  | 'user_actionable'
  | 'invariant';

export function classifyHttpStatus(status?: number | null): ErrorKind {
  if (status == null) return 'unknown';
  if (status === 401) return 'unauthorized';
  if (status === 403) return 'forbidden';
  if (status === 404) return 'not_found';
  if (status === 408) return 'timeout';
  if (status === 429) return 'rate_limited';
  if (status >= 500) return 'server_error';
  if (status >= 400) return 'invalid_data';
  return 'unknown';
}

export function presentationForError(kind: ErrorKind): ErrorPresentation {
  switch (kind) {
    case 'offline':
      return {
        kind,
        recoverability: 'retry_later',
        visibility: 'inline',
        title: "You're offline",
        message: "We'll keep your place in the flow and try again when you're back online.",
        retryable: true,
        preservesUserInput: true,
      };
    case 'timeout':
      return {
        kind,
        recoverability: 'retry_now',
        visibility: 'inline',
        title: 'This is taking too long',
        message: 'Try again. Your current context should stay intact.',
        retryable: true,
        preservesUserInput: true,
      };
    case 'unauthorized':
      return {
        kind,
        recoverability: 'sign_in',
        visibility: 'auth_gate',
        title: 'Sign in to continue',
        message: 'CRAVE should preserve what you were trying to do.',
        retryable: false,
        preservesUserInput: true,
      };
    case 'forbidden':
      return {
        kind,
        recoverability: 'request_access',
        visibility: 'full_state',
        title: "You can't access this yet",
        message: 'This action needs permission or a different account.',
        retryable: false,
        preservesUserInput: true,
      };
    case 'not_found':
      return {
        kind,
        recoverability: 'no_action',
        visibility: 'full_state',
        title: "We couldn't find that",
        message: 'It may have moved, expired, or been removed.',
        retryable: false,
        preservesUserInput: false,
      };
    case 'rate_limited':
      return {
        kind,
        recoverability: 'retry_later',
        visibility: 'inline',
        title: 'Slow down for a moment',
        message: 'Please wait and try again.',
        retryable: true,
        preservesUserInput: true,
      };
    case 'server_error':
      return {
        kind,
        recoverability: 'retry_later',
        visibility: 'full_state',
        title: "CRAVE couldn't load this",
        message: 'Try again in a moment. If it keeps happening, this is on us.',
        retryable: true,
        preservesUserInput: true,
      };
    case 'invalid_data':
      return {
        kind,
        recoverability: 'change_input',
        visibility: 'inline',
        title: "Something doesn't look right",
        message: 'Check the details and try again.',
        retryable: false,
        preservesUserInput: true,
      };
    case 'cancelled':
      return {
        kind,
        recoverability: 'no_action',
        visibility: 'silent_telemetry',
        title: 'Request cancelled',
        message: 'A newer request replaced it.',
        retryable: false,
        preservesUserInput: true,
      };
    case 'unknown':
      return {
        kind,
        recoverability: 'retry_now',
        visibility: 'inline',
        title: "Something went wrong",
        message: 'Try again.',
        retryable: true,
        preservesUserInput: true,
      };
  }
}

export const STALE_TIME = {
  realtime: 0,
  short: 60_000,
  normal: 2 * 60_000,
  long: 10 * 60_000,
  static: 60 * 60_000,
} as const;

export type QueryScope =
  | 'public'
  | 'user'
  | 'place'
  | 'city'
  | 'session';

export type QueryKeyPart = string | number | boolean | null | undefined;

export interface QueryKeyInput {
  scope: QueryScope;
  entity: string;
  userId?: string | null;
  params?: Record<string, QueryKeyPart | readonly QueryKeyPart[]>;
}

function stableParams(params: QueryKeyInput['params']): Record<string, QueryKeyPart | readonly QueryKeyPart[]> | undefined {
  if (!params) return undefined;
  return Object.keys(params)
    .sort()
    .reduce<Record<string, QueryKeyPart | readonly QueryKeyPart[]>>((acc, key) => {
      const value = params[key];
      if (value !== undefined) acc[key] = value;
      return acc;
    }, {});
}

export function foundationQueryKey(input: QueryKeyInput): readonly unknown[] {
  if (input.scope === 'user' && !input.userId) {
    throw new Error('User-scoped queries must include userId for account isolation.');
  }
  if (input.scope !== 'user' && input.userId) {
    throw new Error('Only user-scoped queries may include userId for account isolation.');
  }

  return [
    'crave',
    input.scope,
    input.entity,
    input.scope === 'user' ? input.userId : null,
    stableParams(input.params) ?? null,
  ] as const;
}

export type LinkDestination =
  | { kind: 'place'; placeId: string }
  | { kind: 'rank'; placeId: string }
  | { kind: 'profile'; userId: string }
  | { kind: 'home' };

export interface UniversalLinkContract {
  primaryUrl: string;
  fallbackSchemeUrl: string;
  destination: LinkDestination;
  requiresAuth: boolean;
}

const HTTPS_ORIGIN = 'https://crave.app';
const FALLBACK_SCHEME = 'crave://';

export function placeUniversalLink(placeId: string): UniversalLinkContract {
  const encoded = encodeURIComponent(placeId);
  return {
    primaryUrl: `${HTTPS_ORIGIN}/place/${encoded}`,
    fallbackSchemeUrl: `${FALLBACK_SCHEME}place/${encoded}`,
    destination: { kind: 'place', placeId },
    requiresAuth: false,
  };
}

export type PrivacyScope =
  | 'private'
  | 'shareable'
  | 'display_identity'
  | 'explicit_opt_in';

export type ProvenanceSource =
  | 'user'
  | 'friend'
  | 'restaurant'
  | 'osm'
  | 'overture'
  | 'google_places'
  | 'menu_provider'
  | 'system_inferred'
  | 'unknown';

export type ProvenanceConfidence = 'verified' | 'high' | 'medium' | 'low' | 'unknown';

export interface ProvenanceStamp {
  source: ProvenanceSource;
  fetchedAt: string | null;
  confidence: ProvenanceConfidence;
  privacyScope: PrivacyScope;
}

export interface ProvenanceField<T> {
  value: T;
  provenance: ProvenanceStamp;
}

export function canDisplayProvenanceField<T>(
  field: ProvenanceField<T>,
  viewer: { isOwner?: boolean; hasExplicitOptIn?: boolean },
): boolean {
  switch (field.provenance.privacyScope) {
    case 'private':
      return Boolean(viewer.isOwner);
    case 'shareable':
    case 'display_identity':
      return true;
    case 'explicit_opt_in':
      return Boolean(viewer.hasExplicitOptIn);
  }
}
