import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';
import { secureSessionStorage } from './secureSessionStorage';

const secureMock = SecureStore as unknown as { __reset: () => void };

beforeEach(async () => {
  await AsyncStorage.clear();
  secureMock.__reset();
});

describe('secureSessionStorage', () => {
  it('round-trips a small value through SecureStore', async () => {
    await secureSessionStorage.setItem('sb-project-auth-token', 'short-token-value');
    const value = await secureSessionStorage.getItem('sb-project-auth-token');
    expect(value).toBe('short-token-value');
  });

  it('round-trips a value larger than one SecureStore chunk', async () => {
    // A real Supabase session (access token + refresh token + user JSON)
    // comfortably exceeds a single SecureStore item's practical size limit.
    const large = 'x'.repeat(5000) + 'END';
    await secureSessionStorage.setItem('sb-project-auth-token', large);
    const value = await secureSessionStorage.getItem('sb-project-auth-token');
    expect(value).toBe(large);
    expect(SecureStore.setItemAsync).toHaveBeenCalledWith(
      expect.stringContaining('__manifest'),
      expect.any(String)
    );
  });

  it('round-trips a value containing multi-byte Unicode straddling a chunk boundary, with every chunk under the real byte budget', async () => {
    // Chunking must split by real UTF-8 byte length, not JS string length --
    // a session's user metadata isn't guaranteed to be ASCII-only. The
    // in-memory SecureStore mock doesn't enforce a native size limit, so a
    // round-trip alone can't catch a regression here (a `.slice()` by
    // character count round-trips fine in-memory even though it could
    // exceed the real native per-item byte limit on device) -- assert the
    // real UTF-8 byte length of every stored chunk directly instead.
    const padding = 'a'.repeat(1798); // sits right at the byte-budget edge
    const multiByte = '🍜🍣🥟'.repeat(200); // 4-byte emoji, well past one budget
    const value = padding + multiByte + 'TAIL';

    await secureSessionStorage.setItem('sb-project-auth-token', value);

    const encoder = new TextEncoder();
    const chunkCalls = (SecureStore.setItemAsync as jest.Mock).mock.calls.filter(
      ([key]) => key.includes('__') && !key.endsWith('__manifest')
    );
    expect(chunkCalls.length).toBeGreaterThan(1); // actually exercised multiple chunks
    for (const [, storedValue] of chunkCalls) {
      expect(encoder.encode(storedValue).byteLength).toBeLessThanOrEqual(1800);
    }

    const result = await secureSessionStorage.getItem('sb-project-auth-token');
    expect(result).toBe(value);
  });

  it('a failed chunk write during an overwrite leaves the previous session fully readable', async () => {
    // The real bug this scheme closes: chunks are written under a new
    // generation's keys first, and the manifest only flips to point at the
    // new generation once every one of them has succeeded. A write that
    // fails partway through a refresh-token rotation must never delete or
    // corrupt the session that was live before the rotation started.
    await secureSessionStorage.setItem('sb-project-auth-token', 'original-session-still-valid');

    const large = 'y'.repeat(5000); // forces multiple chunk writes
    (SecureStore.setItemAsync as jest.Mock).mockImplementationOnce(async () => {
      throw new Error('keychain busy mid-rotation');
    });
    await expect(
      secureSessionStorage.setItem('sb-project-auth-token', large)
    ).rejects.toThrow('keychain busy mid-rotation');

    // The old session must still be there, untouched, not a mix of old and
    // new chunks and not gone entirely.
    const stillReadable = await secureSessionStorage.getItem('sb-project-auth-token');
    expect(stillReadable).toBe('original-session-still-valid');
  });

  it('never stores the value in AsyncStorage on write', async () => {
    await secureSessionStorage.setItem('sb-project-auth-token', 'some-session-json');
    const legacy = await AsyncStorage.getItem('sb-project-auth-token');
    expect(legacy).toBeNull();
  });

  it('migrates an existing plaintext AsyncStorage session into SecureStore on first read', async () => {
    // Simulates an already-installed user, upgrading from the old
    // AsyncStorage-only version of this app.
    await AsyncStorage.setItem('sb-project-auth-token', 'legacy-plaintext-session');

    const value = await secureSessionStorage.getItem('sb-project-auth-token');
    expect(value).toBe('legacy-plaintext-session');

    // The plaintext copy must be gone after migration...
    const legacyAfter = await AsyncStorage.getItem('sb-project-auth-token');
    expect(legacyAfter).toBeNull();

    // ...and the value must now be readable straight from SecureStore,
    // with no AsyncStorage involved at all.
    await AsyncStorage.clear();
    const secondRead = await secureSessionStorage.getItem('sb-project-auth-token');
    expect(secondRead).toBe('legacy-plaintext-session');
  });

  it('still returns the legacy value if the SecureStore migration write fails, and retries next launch', async () => {
    await AsyncStorage.setItem('sb-project-auth-token', 'legacy-session-that-fails-to-migrate');
    (SecureStore.setItemAsync as jest.Mock).mockRejectedValueOnce(new Error('keychain busy'));

    const value = await secureSessionStorage.getItem('sb-project-auth-token');
    // The session is still usable this launch even though migration failed.
    expect(value).toBe('legacy-session-that-fails-to-migrate');

    // Migration wasn't marked complete -- the plaintext copy is still there
    // so the next launch's getItem() call retries it.
    const legacyStillThere = await AsyncStorage.getItem('sb-project-auth-token');
    expect(legacyStillThere).toBe('legacy-session-that-fails-to-migrate');
  });

  it('removeItem clears both SecureStore chunks and any legacy AsyncStorage copy', async () => {
    await secureSessionStorage.setItem('sb-project-auth-token', 'to-be-removed');
    await AsyncStorage.setItem('sb-project-auth-token', 'stale-legacy-leftover');

    await secureSessionStorage.removeItem('sb-project-auth-token');

    expect(await secureSessionStorage.getItem('sb-project-auth-token')).toBeNull();
    expect(await AsyncStorage.getItem('sb-project-auth-token')).toBeNull();
  });

  it('returns null when nothing has ever been stored', async () => {
    expect(await secureSessionStorage.getItem('never-set-key')).toBeNull();
  });
});
