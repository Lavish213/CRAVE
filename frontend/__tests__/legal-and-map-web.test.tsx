// Lightweight smoke coverage for the three simplest untested screens:
// the two near-static legal pages (no props, no store, no navigation --
// a render-without-crashing + content-spot-check is proportionate) and
// the web map-fallback stub (whose entire reason to exist is documented
// in its own file: keeping expo-router's route table buildable on web
// without ever importing react-native-maps).
import React from 'react';
import { render } from '@testing-library/react-native';
import TermsOfServiceScreen from '../app/legal/terms';
import PrivacyPolicyScreen from '../app/legal/privacy';
import MapScreenWebFallback from '../app/(tabs)/map.web';

describe('Legal pages', () => {
  it('renders the Terms of Service screen with its title and effective date', () => {
    const { getByText } = render(<TermsOfServiceScreen />);
    expect(getByText('Terms of Service')).toBeTruthy();
    expect(getByText(/Last updated: /)).toBeTruthy();
  });

  it('renders the Privacy Policy screen with its title and effective date', () => {
    const { getByText } = render(<PrivacyPolicyScreen />);
    expect(getByText('Privacy Policy')).toBeTruthy();
    expect(getByText(/Last updated: /)).toBeTruthy();
  });
});

describe('MapScreenWebFallback', () => {
  it('explains the map is unavailable on web, without importing react-native-maps', () => {
    const { getByText } = render(<MapScreenWebFallback />);
    expect(getByText("Map isn't available in the browser preview")).toBeTruthy();
    expect(getByText(/Open CRAVE on iOS or Android/)).toBeTruthy();
  });
});
