// DEAD CODE — this tree lives outside `frontend/`, which is the only Expo
// project that actually builds/ships (see frontend/package.json vs the stub
// root package.json). It was never reachable from the app, its
// uploadService.ts imports a `@/data/client/apiClient` module that doesn't
// exist anywhere in the repo, and its backend calls used a request shape
// the API never accepted (query params vs the JSON body FastAPI expects
// from a bare-scalar POST). Reimplemented for real at:
//   frontend/src/api/upload.ts
//   frontend/src/hooks/useUploadImage.ts
//   frontend/src/hooks/useImageStatusPoll.ts
//   frontend/src/hooks/useImagePicker.ts (needs `npx expo install expo-image-picker`)
// Safe to delete this whole `src/` tree once that's confirmed working.

export { useImagePicker } from './hooks/useImagePicker';
export { useUploadImage } from './hooks/useUploadImage';
export { useImageStatusPoll } from './hooks/useImageStatusPoll';