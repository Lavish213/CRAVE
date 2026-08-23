// src/api/streak.ts
//
// Daily streak gamification (Beli/Duolingo-style). See the backend's
// streak_service.py for the actual day-boundary logic -- this just sends
// the device's current IANA timezone name so the server can compute the
// correct local calendar day; the instant itself always comes from the
// server, never the device clock.
import { client } from './client';

export interface Streak {
  current_streak: number;
  longest_streak: number;
  last_active_date: string | null;
}

function deviceTimezone(): string | undefined {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    return undefined;
  }
}

export async function fetchMyStreak(): Promise<Streak> {
  const { data } = await client.get<Streak>('/api/v1/streak/me');
  return data;
}

// Call this on app open/foreground -- idempotent for the same calendar
// day, so it's safe to call more than once.
export async function pingStreak(): Promise<Streak> {
  const { data } = await client.post<Streak>('/api/v1/streak/ping', {
    timezone: deviceTimezone(),
  });
  return data;
}
