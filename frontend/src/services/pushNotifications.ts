// src/services/pushNotifications.ts
//
// The actual push-notification lifecycle: permission status, contextual
// request + registration, silent re-registration for a returning
// already-granted user, and unregistering this device on sign-out.
// Split out of usePushNotifications.ts (which is now a thin hook wrapper
// around requestOrSilentlyReregister) so Settings' Notifications row can
// call the request/status functions directly without needing a hook.
//
// Real constraint this module works around: an Expo push token is a
// stable per-device-install value (re-fetching it after permission was
// already granted returns the same token, not a new one), which is what
// lets unregisterCurrentDevice() below re-derive "which token is this
// device's" without persisting anything itself.
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
import Constants from 'expo-constants';

import { registerPushToken, unregisterPushToken, PushPlatform } from '../api/account';

export type PushPermissionStatus = 'granted' | 'denied' | 'undetermined' | 'unavailable';

function currentPlatform(): PushPlatform | null {
  if (Platform.OS === 'ios') return 'ios';
  if (Platform.OS === 'android') return 'android';
  return null; // web (or anything else) -- push tokens aren't a thing there
}

function projectId(): string | undefined {
  // Requires extra.eas.projectId in app.json, which a fresh Expo project
  // does NOT have by default (set by `eas init`/`eas build:configure`).
  return Constants.expoConfig?.extra?.eas?.projectId;
}

function isAvailable(): boolean {
  return currentPlatform() !== null && !!projectId();
}

/** Current OS permission status, or 'unavailable' if this platform/build can't do push at all. */
export async function getPushPermissionStatus(): Promise<PushPermissionStatus> {
  if (!isAvailable()) return 'unavailable';
  const { status } = await Notifications.getPermissionsAsync();
  return status as PushPermissionStatus;
}

/**
 * The contextual entry point -- call this only right after showing the
 * user *why* (see settings.tsx), never automatically on app launch.
 * Requests permission if not yet determined, then registers the token.
 * Returns the resulting status so the caller can react (e.g. offer the
 * OS Settings deep link on 'denied').
 */
export async function requestAndRegisterPush(): Promise<PushPermissionStatus> {
  const platform = currentPlatform();
  const pid = projectId();
  if (!platform || !pid) return 'unavailable';

  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let status: PushPermissionStatus = existingStatus as PushPermissionStatus;
  if (status === 'undetermined') {
    const requested = await Notifications.requestPermissionsAsync();
    status = requested.status as PushPermissionStatus;
  }
  if (status !== 'granted') return status;

  try {
    const { data: token } = await Notifications.getExpoPushTokenAsync({ projectId: pid });
    await registerPushToken(token, platform);
  } catch (err) {
    if (__DEV__) console.log('[pushNotifications] registration_failed', err);
  }
  return status;
}

/**
 * Silent, no-prompt re-registration for a returning user who already
 * granted permission in an earlier session -- called from
 * usePushNotifications' effect on every sign-in. Never calls
 * requestPermissionsAsync; a user who hasn't granted yet stays
 * unprompted until they explicitly opt in via Settings.
 */
export async function silentlyReregisterIfGranted(): Promise<void> {
  const platform = currentPlatform();
  const pid = projectId();
  if (!platform || !pid) return;

  try {
    const { status } = await Notifications.getPermissionsAsync();
    if (status !== 'granted') return;
    const { data: token } = await Notifications.getExpoPushTokenAsync({ projectId: pid });
    await registerPushToken(token, platform);
  } catch (err) {
    if (__DEV__) console.log('[pushNotifications] silent_reregister_failed', err);
  }
}

/**
 * Called from authStore's signOut(). Removes this device's registration
 * so a subsequent sign-in by a *different* account on the same device
 * can't have a moderation outcome from the previous account's content
 * still land on it in the narrow window between sign-out and the next
 * sign-in's own registration. Best-effort, matches every other signOut
 * cleanup step -- a failure here must never block sign-out.
 */
export async function unregisterCurrentDevice(): Promise<void> {
  const pid = projectId();
  if (!pid) return;
  try {
    const { status } = await Notifications.getPermissionsAsync();
    if (status !== 'granted') return; // never registered, nothing to remove
    const { data: token } = await Notifications.getExpoPushTokenAsync({ projectId: pid });
    await unregisterPushToken(token);
  } catch (err) {
    if (__DEV__) console.log('[pushNotifications] unregister_failed', err);
  }
}
