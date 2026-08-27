// src/hooks/usePushNotifications.ts
//
// Silently re-registers this device's Expo push token with the backend
// once a user is signed in, *if permission was already granted* in an
// earlier session -- see src/services/pushNotifications.ts for the
// actual lifecycle (status, contextual request, unregister-on-sign-out).
//
// Deliberately never requests permission itself. It used to call
// requestPermissionsAsync() automatically on every sign-in, with no
// explanation shown first -- the contextual request now lives behind
// the Notifications row in Settings (see app/settings.tsx), which
// explains the benefit before asking. This effect only keeps an
// already-granted registration fresh; a user who hasn't opted in yet
// stays unprompted.
import { useEffect } from 'react';

import { silentlyReregisterIfGranted } from '../services/pushNotifications';

export function usePushNotifications(userId: string | null | undefined): void {
  useEffect(() => {
    if (!userId) return;
    silentlyReregisterIfGranted().catch(() => {});
  }, [userId]);
}
