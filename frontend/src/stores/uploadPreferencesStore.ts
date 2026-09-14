// uploadPreferencesStore.ts
//
// A single user-facing preference: require Wi-Fi before uploading queued
// videos (real, multi-MB files -- unlike photos, worth letting a user opt
// out of burning cellular data on). Defaults to *off* -- videos already
// upload on any connection today, and turning this on by default would be
// a silent behavior regression (queued videos suddenly stop uploading on
// cellular with no explanation) rather than a new opt-in safety feature.
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';

interface UploadPreferencesStore {
  wifiOnlyVideoUploads: boolean;
  setWifiOnlyVideoUploads: (value: boolean) => void;
}

export const useUploadPreferencesStore = create<UploadPreferencesStore>()(
  persist(
    (set) => ({
      wifiOnlyVideoUploads: false,
      setWifiOnlyVideoUploads: (value: boolean) => set({ wifiOnlyVideoUploads: value }),
    }),
    {
      name: 'crave-upload-preferences',
      storage: createJSONStorage(() => AsyncStorage),
    }
  )
);

// Confirmed CodeRabbit finding on PR #312: this store's `false` default
// is live the instant the module loads, but the real (possibly `true`)
// persisted value only lands once AsyncStorage's rehydration resolves --
// a real async gap, not merely a same-tick formality. A caller that reads
// `wifiOnlyVideoUploads` before that resolves (videoQueueStore.ts's
// runSyncPass, triggered by a foreground/connectivity event that can fire
// this early) would silently treat a user's real "Wi-Fi only" preference
// as off and upload over cellular. Awaited once at the top of that gate,
// not cached, since a single in-flight hydration only ever needs to
// resolve once.
export function waitForUploadPreferencesHydration(): Promise<void> {
  if (useUploadPreferencesStore.persist.hasHydrated()) return Promise.resolve();
  return new Promise((resolve) => {
    const unsubscribe = useUploadPreferencesStore.persist.onFinishHydration(() => {
      unsubscribe();
      resolve();
    });
  });
}
