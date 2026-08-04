// app.config.js
//
// Dynamic overlay on top of app.json — everything static stays in
// app.json; this file only injects the one thing that can't safely live
// in a committed JSON file: the Android Google Maps API key, read from an
// environment variable instead of a literal string in source control.
//
// Why Android only: react-native-maps defaults to Apple's native MapKit
// on iOS unless a screen explicitly sets provider="google" (this app's
// map screen — app/(tabs)/map.tsx — doesn't), so iOS needs no key here.
// Android has no native-maps equivalent; it always renders via Google
// Maps and the app is a blank gray box without this key configured.
//
// Set GOOGLE_MAPS_ANDROID_API_KEY in a local, gitignored .env for
// `expo start` / `expo run:android`, and as an EAS secret
// (`eas secret:create --name GOOGLE_MAPS_ANDROID_API_KEY --value <key>`)
// for EAS Build. Restrict the key itself (GCP Credentials page) to
// Android apps — package com.crave.app + your signing SHA-1 — not just
// by API allowlist, since this key ships inside the compiled binary.
const appJson = require('./app.json');

module.exports = ({ config }) => {
  const base = appJson.expo;
  return {
    ...config,
    ...base,
    android: {
      ...base.android,
      config: {
        ...base.android?.config,
        googleMaps: {
          apiKey: process.env.GOOGLE_MAPS_ANDROID_API_KEY,
        },
      },
    },
  };
};
