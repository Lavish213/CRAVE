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
