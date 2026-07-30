import { withImageWidth, MAX_IMAGE_WIDTH } from './imageUrl';

describe('withImageWidth', () => {
  it('sets the w param on an absolute proxy URL', () => {
    const result = withImageWidth(
      'https://api.example.com/api/v1/image?ref=places/abc/photos/xyz',
      1600,
    );
    expect(result).toContain('w=1600');
    expect(result).toContain('ref=places');
  });

  it('replaces an existing w param rather than appending a second one', () => {
    const result = withImageWidth(
      'https://api.example.com/api/v1/image?ref=places/abc/photos/xyz&w=800',
      1600,
    );
    expect(result).toContain('w=1600');
    expect(result).not.toContain('w=800');
    expect(result!.match(/w=/g)).toHaveLength(1);
  });

  it('preserves a relative proxy URL as relative', () => {
    const result = withImageWidth('/api/v1/image?ref=places/abc/photos/xyz', 1600);
    expect(result).toBe('/api/v1/image?ref=places%2Fabc%2Fphotos%2Fxyz&w=1600');
  });

  it('leaves non-proxy URLs untouched', () => {
    // Uploaded photos come straight from R2 and may carry a signature that
    // an extra query param would invalidate.
    const r2 = 'https://bucket.account.r2.cloudflarestorage.com/places/1/processed/2.jpg';
    expect(withImageWidth(r2, 1600)).toBe(r2);

    const google = 'https://lh3.googleusercontent.com/places/abc=s1600';
    expect(withImageWidth(google, 800)).toBe(google);
  });

  it('returns null for null/undefined/empty input', () => {
    expect(withImageWidth(null, 800)).toBeNull();
    expect(withImageWidth(undefined, 800)).toBeNull();
    expect(withImageWidth('', 800)).toBeNull();
  });

  it('exposes a max width matching the backend proxy clamp', () => {
    expect(MAX_IMAGE_WIDTH).toBe(1600);
  });
});
