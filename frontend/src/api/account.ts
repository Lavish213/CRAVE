// src/api/account.ts
//
// Backend routes: POST/DELETE /api/v1/account/push-token (see
// backend/app/api/v1/routes/account.py). Used by
// src/hooks/usePushNotifications.ts to register/unregister this device's
// Expo push token for the signed-in account.
import { client } from './client';

export type PushPlatform = 'ios' | 'android';

export async function registerPushToken(pushToken: string, platform: PushPlatform): Promise<void> {
  await client.post('/api/v1/account/push-token', { push_token: pushToken, platform });
}

export async function unregisterPushToken(pushToken: string): Promise<void> {
  await client.delete(`/api/v1/account/push-token/${encodeURIComponent(pushToken)}`);
}
