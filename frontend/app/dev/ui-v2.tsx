import React from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import {
  ConfidenceStatement,
  ConstraintToken,
  CraveMapPin,
  DecisionRecovery,
  EvidenceLimitation,
  FoodMedia,
  OperationalStatus,
  PlaceResultHero,
  PlaceResultSupporting,
} from '../../src/ui-v2/components';
import { CraveButton, CraveSurface, CraveText } from '../../src/ui-v2/primitives';
import { uiColors, uiSpace } from '../../src/ui-v2/tokens';
import { hostilePhotoUrls, searchMapFixtures } from '../../src/ui-v2/fixtures/searchMapFixtures';

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <CraveText role="title">{title}</CraveText>
      {children}
    </View>
  );
}

export default function UiV2LabScreen() {
  if (!__DEV__) {
    return (
      <CraveSurface tone="canvas" style={styles.unavailable}>
        <CraveText role="title">UI Lab is development-only.</CraveText>
      </CraveSurface>
    );
  }

  const noop = () => {};

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <CraveText role="headline">CRAVE UI V2 Lab</CraveText>
        <CraveText role="body" tone="secondary">
          Production components under normal, hostile-data, recovery, and uncertainty states. This is design proof, not device verification.
        </CraveText>
      </View>

      <Section title="Result hierarchy">
        <PlaceResultHero
          place={searchMapFixtures.goodPhoto}
          onPress={noop}
          reasonKind="bestMatch"
          reason="Great fit for a flavorful dinner nearby."
          confidence="strong"
          operationalState="open"
          action={<CraveButton label="Save" onPress={noop} />}
        />
        <PlaceResultSupporting
          place={searchMapFixtures.supporting}
          onPress={noop}
          reasonKind="saferPick"
          reason="A familiar cuisine with a little less travel."
          confidence="moderate"
        />
        <PlaceResultSupporting
          place={searchMapFixtures.longName}
          onPress={noop}
          reasonKind="worthExploring"
          reason="Different from your recent saves, but it matches the food intent."
          confidence="personalizationLearning"
          limitation="tasteUnverified"
        />
      </Section>

      <Section title="Missing and failed media">
        <PlaceResultHero
          place={searchMapFixtures.noPhoto}
          onPress={noop}
          reasonKind="worthExploring"
          reason="The match comes from place data, not a photo."
          limitation="photoUnavailable"
        />
        <FoodMedia source={hostilePhotoUrls.failed} placeName="Failed image fixture" variant="supporting" />
      </Section>

      <Section title="Photo torture">
        <FoodMedia source={hostilePhotoUrls.veryDark} placeName="Very dark photo" variant="supporting" />
        <FoodMedia source={hostilePhotoUrls.portrait} placeName="Portrait crop" variant="supporting" />
        <FoodMedia source={hostilePhotoUrls.overexposed} placeName="Bright photo" variant="supporting" />
      </Section>

      <Section title="Evidence and operational truth">
        <OperationalStatus state="open" />
        <OperationalStatus state="closed" />
        <OperationalStatus state="stale" />
        <OperationalStatus state="unknown" />
        <ConfidenceStatement confidence="strong" />
        <ConfidenceStatement confidence="moderate" />
        <ConfidenceStatement confidence="personalizationLearning" />
        <EvidenceLimitation kind="hoursStale" />
        <EvidenceLimitation kind="menuLimited" />
        <EvidenceLimitation kind="fewMatchingSaves" />
      </Section>

      <Section title="Constraints">
        <View style={styles.wrapRow}>
          <ConstraintToken label="Halal" kind="protected" />
          <ConstraintToken label="Nearby" />
          <ConstraintToken label="$$" kind="relaxed" />
        </View>
      </Section>

      <Section title="Map states">
        <View style={styles.wrapRow}>
          <CraveMapPin label="Night Market Kitchen" />
          <CraveMapPin label="Night Market Kitchen" selected />
          <CraveMapPin label="After Hours Ramen" closed />
          <CraveMapPin clusterCount={7} />
        </View>
      </Section>

      <Section title="Recovery">
        <DecisionRecovery
          kind="requiredZero"
          protectedConstraint="Halal"
          title="No verified matches"
          body="CRAVE can’t verify this safely from the current data, so it won’t loosen the protected constraint."
          secondaryLabel="Edit search"
          onSecondary={noop}
        />
        <DecisionRecovery
          kind="preferredNoExact"
          title="No exact budget match"
          body="Nearby places still respect your protected constraints."
          primaryLabel="See nearby options"
          onPrimary={noop}
          secondaryLabel="Edit search"
          onSecondary={noop}
        />
        <DecisionRecovery
          kind="locationDenied"
          title="Location is off"
          body="Choose an area to keep searching without sharing your location."
          primaryLabel="Choose area"
          onPrimary={noop}
        />
      </Section>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: uiColors.surface.canvas,
  },
  content: {
    padding: uiSpace.screenGutter,
    paddingBottom: uiSpace.xxl,
    gap: uiSpace.sectionGap,
  },
  header: {
    gap: uiSpace.sm,
  },
  section: {
    gap: uiSpace.md,
  },
  wrapRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: uiSpace.sm,
  },
  unavailable: {
    flex: 1,
    padding: uiSpace.screenGutter,
    justifyContent: 'center',
  },
});
