import { relativeTime } from './time';

describe('relativeTime', () => {
  it('returns "just now" for sub-minute timestamps', () => {
    expect(relativeTime(new Date().toISOString())).toBe('just now');
  });

  it('formats minutes', () => {
    const iso = new Date(Date.now() - 5 * 60_000).toISOString();
    expect(relativeTime(iso)).toBe('5m ago');
  });

  it('formats hours', () => {
    const iso = new Date(Date.now() - 3 * 3_600_000).toISOString();
    expect(relativeTime(iso)).toBe('3h ago');
  });

  it('formats days under a week', () => {
    const iso = new Date(Date.now() - 2 * 86_400_000).toISOString();
    expect(relativeTime(iso)).toBe('2d ago');
  });

  it('falls back to a locale date at a week or older', () => {
    const iso = new Date(Date.now() - 10 * 86_400_000).toISOString();
    expect(relativeTime(iso)).not.toMatch(/ago$/);
  });

  it('returns empty string for an unparseable timestamp', () => {
    expect(relativeTime('not-a-date')).toBe('');
  });
});
