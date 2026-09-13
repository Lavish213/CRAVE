// Legacy deep-link handoff. Useful social evidence now belongs on Feed;
// keeping this route as a redirect avoids breaking old links during retirement.
import React from 'react';
import { Redirect } from 'expo-router';

export default function FriendsFeedRedirect() {
  return <Redirect href="/" />;
}
