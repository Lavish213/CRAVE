// The standalone social leaderboard is outside V1. Preserve old links with a
// controlled handoff to Profile rather than exposing a stale vanity surface.
import React from 'react';
import { Redirect } from 'expo-router';

export default function LeaderboardRedirect() {
  return <Redirect href="/profile" />;
}
