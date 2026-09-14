/**
 * secureSessionStorage.ts
 *
 * Supabase's auth client was configured with the plain AsyncStorage adapter,
 * so the session (access token + refresh token) sat unencrypted on-device --
 * readable by anything with filesystem access (a rooted device, a device
 * backup extraction, another app on a compromised device). This adapter
 * moves the same storage onto expo-secure-store (iOS Keychain / Android
 * Keystore) instead, implementing the same
 * {getItem, setItem, removeItem} shape supabase-js's `storage` option
 * expects (AsyncStorage already matched this shape, which is why swapping
 * it in was a one-line change at the call site).
 *
 * SecureStore enforces a practical per-item size limit well under what a
 * Supabase session JSON (access token + refresh token + user metadata) can
 * reach, so a value is split across multiple small SecureStore items. This
 * still stores everything encrypted-at-rest; it never falls back to a
 * larger, unencrypted store for the parts that don't fit.
 *
 * Chunks are addressed by *generation*, not overwritten in place: a manifest
 * item ({key}__manifest = "{gen}:{count}") names which generation is live.
 * setSecure() writes every chunk of the *new* generation under fresh keys
 * first, and only flips the manifest to point at it once all of them have
 * succeeded -- the previous generation's chunks are left completely
 * untouched until that point, and only cleaned up afterward. A write
 * failure partway through a refresh-token rotation therefore never deletes
 * or corrupts the session that's still live; the manifest keeps naming the
 * old generation until a new one has been fully committed. (An earlier
 * version of this file deleted the old chunks before writing the new ones,
 * which could silently sign a real user out if any single chunk write
 * failed mid-rotation -- caught in review before merge, not in production.)
 *
 * Chunking splits by real UTF-8 byte length, walking whole Unicode code
 * points (not JS's UTF-16 string units) so a chunk boundary can never land
 * inside a multi-byte character or a surrogate pair -- a session's user
 * metadata isn't guaranteed to be ASCII-only, and SecureStore's native size
 * limit is a byte limit, not a JS string-length limit.
 *
 * Migration for already-installed users: getItem() checks SecureStore
 * first, and only if that's empty falls back to reading the legacy
 * AsyncStorage value under the same key (whatever key supabase-js happens
 * to compute internally -- this adapter doesn't need to know it), moves it
 * into SecureStore, and deletes the plaintext copy. If the migration write
 * itself fails, the legacy value is still returned so a real device isn't
 * signed out over it -- the migration simply retries on the next read.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';

// Conservative margin under SecureStore's practical per-item limit
// (documented around 2048 bytes on the more restrictive platform), and this
// is a true byte budget -- see splitByUtf8ByteBudget below.
const CHUNK_BYTE_BUDGET = 1800;
const MANIFEST_SUFFIX = '__manifest';

interface Manifest {
  gen: number;
  count: number;
}

function chunkKey(key: string, gen: number, index: number): string {
  return `${key}__${gen}__${index}`;
}

async function readManifest(key: string): Promise<Manifest | null> {
  const raw = await SecureStore.getItemAsync(`${key}${MANIFEST_SUFFIX}`);
  if (!raw) return null;
  const [genRaw, countRaw] = raw.split(':');
  const gen = parseInt(genRaw, 10);
  const count = parseInt(countRaw, 10);
  if (!Number.isFinite(gen) || !Number.isFinite(count) || count <= 0) return null;
  return { gen, count };
}

function utf8ByteLengthOfCodePoint(codePoint: number): number {
  if (codePoint < 0x80) return 1;
  if (codePoint < 0x800) return 2;
  if (codePoint < 0x10000) return 3;
  return 4;
}

/**
 * Splits `value` into pieces whose real UTF-8 byte size never exceeds
 * `maxBytes`, breaking only between whole Unicode code points (`for...of`
 * over a string iterates code points, correctly treating a surrogate pair
 * as one unit) so a multi-byte character is never split across chunks.
 */
function splitByUtf8ByteBudget(value: string, maxBytes: number): string[] {
  const chunks: string[] = [];
  let current = '';
  let currentBytes = 0;

  for (const char of value) {
    const codePoint = char.codePointAt(0) ?? 0;
    const charBytes = utf8ByteLengthOfCodePoint(codePoint);
    if (currentBytes + charBytes > maxBytes && current.length > 0) {
      chunks.push(current);
      current = '';
      currentBytes = 0;
    }
    current += char;
    currentBytes += charBytes;
  }
  if (current.length > 0 || chunks.length === 0) {
    chunks.push(current);
  }
  return chunks;
}

async function deleteGeneration(key: string, gen: number, count: number): Promise<void> {
  for (let i = 0; i < count; i++) {
    await SecureStore.deleteItemAsync(chunkKey(key, gen, i)).catch(() => undefined);
  }
}

async function getSecure(key: string): Promise<string | null> {
  const manifest = await readManifest(key);
  if (!manifest) return null;

  const parts: string[] = [];
  for (let i = 0; i < manifest.count; i++) {
    const part = await SecureStore.getItemAsync(chunkKey(key, manifest.gen, i));
    if (part === null) {
      // A partial/corrupted write -- treat as absent rather than returning
      // a truncated session, so the caller falls through to a clean
      // sign-in instead of a malformed token.
      return null;
    }
    parts.push(part);
  }
  return parts.join('');
}

async function setSecure(key: string, value: string): Promise<void> {
  const previous = await readManifest(key);
  const newGen = (previous?.gen ?? 0) + 1;

  const parts = splitByUtf8ByteBudget(value, CHUNK_BYTE_BUDGET);
  for (let i = 0; i < parts.length; i++) {
    await SecureStore.setItemAsync(chunkKey(key, newGen, i), parts[i]);
  }

  // Commit point. Every chunk of the new generation is written and
  // confirmed before this line runs; if any write above throws instead,
  // the manifest still names `previous`, whose chunks were never touched.
  await SecureStore.setItemAsync(`${key}${MANIFEST_SUFFIX}`, `${newGen}:${parts.length}`);

  // The new generation is live -- best-effort clean up the old one now.
  // A failure here just leaves harmless orphaned keys; they're never read
  // again since the manifest no longer points at them.
  if (previous) {
    await deleteGeneration(key, previous.gen, previous.count);
  }
}

async function removeSecure(key: string): Promise<void> {
  const manifest = await readManifest(key);
  if (!manifest) return;
  // Delete the manifest first: if the process dies partway through this
  // function, a reader must see "nothing stored," never a manifest
  // pointing at chunks that are half-deleted.
  await SecureStore.deleteItemAsync(`${key}${MANIFEST_SUFFIX}`);
  await deleteGeneration(key, manifest.gen, manifest.count);
}

async function getItem(key: string): Promise<string | null> {
  const secure = await getSecure(key);
  if (secure !== null) return secure;

  const legacy = await AsyncStorage.getItem(key);
  if (legacy === null) return null;

  try {
    await setSecure(key, legacy);
    await AsyncStorage.removeItem(key);
  } catch (err) {
    console.warn(
      'secureSessionStorage: migration to SecureStore failed, will retry next launch',
      err
    );
  }
  return legacy;
}

async function setItem(key: string, value: string): Promise<void> {
  await setSecure(key, value);
  // Defensive: clears a legacy plaintext copy even if it's a refresh-token
  // rotation that ran before getItem() ever had a chance to migrate it.
  await AsyncStorage.removeItem(key).catch(() => undefined);
}

async function removeItem(key: string): Promise<void> {
  await removeSecure(key);
  await AsyncStorage.removeItem(key).catch(() => undefined);
}

export const secureSessionStorage = { getItem, setItem, removeItem };
