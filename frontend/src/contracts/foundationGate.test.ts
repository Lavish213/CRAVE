import {
  canDisplayProvenanceField,
  classifyHttpStatus,
  foundationQueryKey,
  placeUniversalLink,
  presentationForError,
  type ProvenanceField,
} from './foundationGate';

describe('Foundation Gate contracts', () => {
  it('maps statuses and auth/cancelled presentations predictably', () => {
    expect(classifyHttpStatus(401)).toBe('unauthorized');
    expect(classifyHttpStatus(403)).toBe('forbidden');
    expect(classifyHttpStatus(404)).toBe('not_found');
    expect(classifyHttpStatus(408)).toBe('timeout');
    expect(classifyHttpStatus(429)).toBe('rate_limited');
    expect(classifyHttpStatus(500)).toBe('server_error');
    expect(classifyHttpStatus(422)).toBe('invalid_data');
    expect(presentationForError('unauthorized')).toMatchObject({
      visibility: 'auth_gate',
      recoverability: 'sign_in',
      preservesUserInput: true,
    });
    expect(presentationForError('cancelled')).toMatchObject({
      visibility: 'silent_telemetry',
      retryable: false,
    });
  });

  it('locks account-isolated, deterministic query keys', () => {
    expect(() => foundationQueryKey({ scope: 'user', entity: 'saves' })).toThrow(/userId/);
    expect(JSON.stringify(foundationQueryKey({
      scope: 'place',
      entity: 'detail',
      params: { b: 2, a: 1, ignored: undefined },
    }))).toBe(JSON.stringify(foundationQueryKey({
      scope: 'place',
      entity: 'detail',
      params: { a: 1, b: 2 },
    })));
  });

  it('uses https links first and keeps crave scheme fallback', () => {
    expect(placeUniversalLink('place/with space')).toMatchObject({
      primaryUrl: 'https://crave.app/place/place%2Fwith%20space',
      fallbackSchemeUrl: 'crave://place/place%2Fwith%20space',
      destination: { kind: 'place', placeId: 'place/with space' },
    });
  });

  it('enforces privacy scopes independently from provenance source', () => {
    const field: ProvenanceField<string> = {
      value: 'shared favorite dish',
      provenance: {
        source: 'user',
        fetchedAt: '2026-09-11T00:00:00Z',
        confidence: 'verified',
        privacyScope: 'explicit_opt_in',
      },
    };

    expect(canDisplayProvenanceField(field, { hasExplicitOptIn: false })).toBe(false);
    expect(canDisplayProvenanceField(field, { hasExplicitOptIn: true })).toBe(true);
  });
});
