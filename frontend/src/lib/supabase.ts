import { createClient } from '@supabase/supabase-js';
import AsyncStorage from '@react-native-async-storage/async-storage';

const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL ?? '';
const supabaseAnonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? '';

// Whether real config is present. `app/_layout.tsx` checks this and renders
// a plain-language configuration-error screen instead of the app when
// false. This has to be a value checked at render time, not a thrown
// error here: this module executes at import time, before any React tree
// (including the root ErrorBoundary) exists to catch a throw -- a missing
// env var previously crashed the entire app with a raw
// "supabaseUrl is required." error before a single screen ever rendered.
export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey);

// A syntactically-valid placeholder so createClient() never throws when
// config is missing -- the real gate is isSupabaseConfigured above, not
// whether this client can be constructed. Nothing calls through this
// client when isSupabaseConfigured is false, since _layout.tsx renders
// the configuration-error screen instead of the app.
export const supabase = createClient(
  supabaseUrl || 'https://placeholder.supabase.co',
  supabaseAnonKey || 'placeholder-anon-key',
  {
    auth: {
      storage: AsyncStorage,
      autoRefreshToken: true,
      persistSession: true,
      detectSessionInUrl: false,
    },
  }
);
