import axios from 'axios';
import { supabase } from '../lib/supabase';

const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';
const API_KEY = process.env.EXPO_PUBLIC_API_KEY ?? '';

export const client = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
    ...(API_KEY ? { 'x-api-key': API_KEY } : {}),
  },
});

// Previously nothing ever attached the Supabase session token, so every
// backend route guarded by get_current_user_id (saves, hitlist, upload) was
// unreachable from the app regardless of sign-in state — the request would
// always 401 with "Missing bearer token". The session already exists in
// authStore/supabase; this just attaches it the way supabase-js recommends:
// (await supabase.auth.getSession()).data.session.access_token.
client.interceptors.request.use(async (config) => {
  const requestId = Math.random().toString(36).slice(2) + Date.now().toString(36);
  config.headers['X-Request-ID'] = requestId;

  try {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
  } catch (err) {
    // No/expired session — request proceeds unauthenticated and the backend
    // will 401 it if the route requires a user, which the caller already
    // handles (see cravesStore's _classifyError 'auth_required' path).
    if (__DEV__) console.warn('[client] failed to attach session token', err);
  }

  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 429) {
      error.message = 'Rate limit reached. Please wait a moment.';
    }
    return Promise.reject(error);
  },
);
