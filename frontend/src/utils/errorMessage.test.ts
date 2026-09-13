import { errorMessageFor } from './errorMessage';

describe('errorMessageFor', () => {
  it('returns the rate-limit-specific message for a 429', () => {
    expect(errorMessageFor({ response: { status: 429 } }, 'fallback')).toBe(
      "You're doing that too fast — wait a moment and try again.",
    );
  });

  it('returns the offline-specific message when there is no response at all', () => {
    expect(errorMessageFor(new Error('network unreachable'), 'fallback')).toBe(
      "Can't reach CRAVE — check your connection.",
    );
    expect(errorMessageFor(null, 'fallback')).toBe("Can't reach CRAVE — check your connection.");
    expect(errorMessageFor(undefined, 'fallback')).toBe("Can't reach CRAVE — check your connection.");
  });

  it('falls back to the caller-provided message for any other response status', () => {
    expect(errorMessageFor({ response: { status: 500 } }, 'Could not load places')).toBe(
      'Could not load places',
    );
    expect(errorMessageFor({ response: { status: 404 } }, 'Could not load places')).toBe(
      'Could not load places',
    );
  });
});
