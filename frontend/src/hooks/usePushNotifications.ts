// src/hooks/usePushNotifications.ts
//
// Registers this device's Expo push token with the backend
// (POST /account/push-token, see src/api/account.ts) once a user is
// signed in -- the notification content itself (video approved/
// rejected) is sent server-side from video_processing_worker.py.
//
// Deliberately does NOT unregister on sign-out: DevicePushToken is keyed
// by the token itself, not the user (see backend/app/db/models/
// device_push_token.py's docstring) specifically so a device signing
// into a different account just moves the existing registration rather
// than needing an explicit unregister/re-register dance here.
//
// Best-effort throughout -- matches every other secondary/background
// concern in this app (see pingStreak's own .catch(() => {}) in
// app/_layout.tsx). A failure here (permission denied, no EAS project
// configured, network error) must never be user-visible or block
// anything else the app does.
//
// Requires extra.eas.projectId in app.json, which a fresh Expo project
// does NOT have by default (set by `eas init`/`eas build:configure`,
// something this hook can't do for itself) -- until that's set, this
// intentionally no-ops rather than throwing.
import { useEffect } from 'react';
import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import Constants from 'expo-constants';

import { registerPushToken, PushPlatform } from '../api/account';

function currentPlatform(): PushPlatform | null {
  if (Platform.OS === 'ios') return 'ios';
  if (Platform.OS === 'android') return 'android';
  return null; // web (or anything else) -- push tokens aren't a thing there
}

export function usePushNotifications(userId: string | null | undefined): void {
  useEffect(() => {
    if (!userId) return;
    const platform = currentPlatform();
    if (!platform) return;

    let cancelled = false;

    (async () => {
      try {
        const projectId = Constants.expoConfig?.extra?.eas?.projectId;
        if (!projectId) {
          if (__DEV__) {
            console.log(
              '[usePushNotifications] no extra.eas.projectId in app.json -- skipping ' +
                '(run `eas init` to enable push notification registration)'
            );
          }
          return;
        }

        const { status: existingStatus } = await Notifications.getPermissionsAsync();
        let status = existingStatus;
        if (status !== 'granted') {
          const requested = await Notifications.requestPermissionsAsync();
          status = requested.status;
        }
        if (status !== 'granted' || cancelled) return;

        const { data: token } = await Notifications.getExpoPushTokenAsync({ projectId });
        if (cancelled) return;

        await registerPushToken(token, platform);
      } catch (err) {
        if (__DEV__) console.log('[usePushNotifications] registration_failed', err);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [userId]);
}
