// react-native-maps has no real web support: it ships a MapView.web.js,
// but its own lib/index.js barrel unconditionally also re-exports Marker
// (MapMarker.js), which imports react-native's native-only
// codegenNativeCommands — Metro fails to resolve that on web with a hard
// bundling error, not a runtime one. Worse, expo-router's file-based
// routing uses require.context to eagerly bundle every file under app/ (so
// it can build its route table) regardless of which screen is actually
// active — so that one unresolvable import previously failed the ENTIRE
// web bundle, not just the Map tab, leaving every screen blank. A
// platform-specific app/(tabs)/map.web.tsx alone doesn't fix this: Metro's
// require.context still statically requires app/(tabs)/map.tsx too (both
// files match its route-file glob), so map.tsx's bad import still poisons
// the bundle even though it's never the screen actually rendered on web.
// Redirecting the whole package to Metro's built-in "empty module"
// resolution for the web platform is what actually stops that failure at
// its source — nothing on web needs react-native-maps' real exports, since
// map.web.tsx replaces the screen instead.
const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

// Separately: zustand's package.json "exports" map offers an ESM build
// (esm/middleware.mjs) that uses `import.meta.env` for a Vite-specific
// devtools check. Metro's web platform condition is just ['browser'],
// which zustand's exports map doesn't declare at all for these subpaths —
// but Metro still resolves `import ... from 'zustand/middleware'` to the
// ESM build over the CJS one (index.js/middleware.js), and Metro's output
// format can't execute `import.meta` at all, crashing every screen at
// runtime with "Cannot use 'import.meta' outside a module." Setting
// unstable_conditionNames directly didn't change this resolution — the
// exports map itself is the problem, so ignore it entirely and fall back
// to resolverMainFields (['react-native', 'browser', 'main']) below, which
// for zustand's plain "main": "./index.js" always lands on the CJS build
// regardless of platform.
config.resolver.unstable_enablePackageExports = false;

const upstreamResolveRequest = config.resolver.resolveRequest;

config.resolver.resolveRequest = (context, moduleName, platform) => {
  if (platform === 'web' && moduleName === 'react-native-maps') {
    return { type: 'empty' };
  }
  return upstreamResolveRequest
    ? upstreamResolveRequest(context, moduleName, platform)
    : context.resolveRequest(context, moduleName, platform);
};

module.exports = config;
