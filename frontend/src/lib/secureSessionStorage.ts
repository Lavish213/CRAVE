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
 * reach, so a value is split across multiple small SecureStore items
 * ({key}__0, {key}__1, ...) plus a small {key}__chunks item recording how
 * many. This still stores everything encrypted-at-rest; it never falls back
 * to a larger, unencrypted store for the parts that don't fit.
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
// (documented around 2048 bytes on the more restrictive platform).
const CHUNK_SIZE = 1800;
const CHUNK_COUNT_SUFFIX = '__chunks';

function chunkKey(key: string, index: number): string {
  return `${key}__${index}`;
}

async function readChunkCount(key: string): Promise<number> {
  const raw = await SecureStore.getItemAsync(`${key}${CHUNK_COUNT_SUFFIX}`);
  if (!raw) return 0;
  const count = parseInt(raw, 10);
  return Number.isFinite(count) && count > 0 ? count : 0;
}

async function getSecure(key: string): Promise<string | null> {
  const count = await readChunkCount(key);
  if (count === 0) return null;

  const parts: string[] = [];
  for (let i = 0; i < count; i++) {
    const part = await SecureStore.getItemAsync(chunkKey(key, i));
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
  await removeSecure(key);
  const count = Math.max(1, Math.ceil(value.length / CHUNK_SIZE));
  for (let i = 0; i < count; i++) {
    const part = value.slice(i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE);
    await SecureStore.setItemAsync(chunkKey(key, i), part);
  }
  await SecureStore.setItemAsync(`${key}${CHUNK_COUNT_SUFFIX}`, String(count));
}

async function removeSecure(key: string): Promise<void> {
  const count = await readChunkCount(key);
  for (let i = 0; i < count; i++) {
    await SecureStore.deleteItemAsync(chunkKey(key, i));
  }
  await SecureStore.deleteItemAsync(`${key}${CHUNK_COUNT_SUFFIX}`);
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
