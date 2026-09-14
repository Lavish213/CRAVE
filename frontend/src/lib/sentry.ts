// Sentry crash/error reporting for the CRAVE mobile app.
//
// Mirrors the backend's own guard (`if settings.sentry_dsn:` in
// backend/app/main.py, see docs/PRODUCTION_ENVIRONMENT_MANIFEST.md for the
// full env-var picture): with no DSN configured, `Sentry.init()` is never
// called at all -- nothing native is touched, nothing crashes, and nothing
// is ever sent anywhere. This is the app's only crash/error reporting today;
// before this file existed a real crash on a user's device was invisible to
// the team even though the backend has been reporting to Sentry for a while.
//
// Once a real DSN is provisioned (see frontend/.env.example and
// docs/PRODUCTION_ENVIRONMENT_MANIFEST.md), set EXPO_PUBLIC_SENTRY_DSN as an
// EAS environment variable for the production profile and this starts
// reporting automatically -- no code change needed here.
import * as Sentry from '@sentry/react-native';

const dsn = process.env.EXPO_PUBLIC_SENTRY_DSN;

// Exported so a screen (e.g. a debug/about screen) could show whether crash
// reporting is actually active, the same way isSupabaseConfigured is used.
export const isSentryConfigured = Boolean(dsn);

export function initSentry(): void {
  if (!dsn) return;

  Sentry.init({
    dsn,
    environment: __DEV__ ? 'development' : 'production',
    // Matches the backend's traces_sample_rate=0.1 -- a light sample of
    // performance data, not full tracing on every request.
    tracesSampleRate: 0.1,
    // Matches the backend's send_default_pii=False -- never attach device
    // identifiers/user PII to events beyond what we explicitly choose to.
    sendDefaultPii: false,
  });
}
