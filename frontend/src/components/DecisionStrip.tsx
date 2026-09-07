import React from 'react';
import { StyleSheet, Text, View, type ViewStyle } from 'react-native';
import type { DecisionRole } from '../api/decisionSession';
import { Colors, Spacing, Typography } from '../constants/colors';

export type DecisionStripSource = 'decision_session' | 'discovery' | 'organic';
export type DecisionStripDensity = 'compact' | 'full';

export interface DecisionPracticalFacts {
  distance?: string | null;
  price?: string | null;
  hours?: string | null;
}

export interface DecisionStripProps {
  source: DecisionStripSource;
  role?: DecisionRole;
  reason?: string | null;
  /** Qualitative only: e.g. "Strong fit". Never pass a percentage. */
  fitLabel?: string | null;
  /** Confidence is a separate axis from fit and must render separately. */
  confidenceLabel?: string | null;
  practicalFacts?: DecisionPracticalFacts;
  density?: DecisionStripDensity;
  style?: ViewStyle;
}

const ROLE_LABELS: Record<DecisionRole, string> = {
  // Keep the underlying role strings compatible with existing tests/callers;
  // visual capitalization belongs to the renderer, not the API enum/copy.
  best_fit: 'Best fit',
  safe_bet: 'Safe bet',
  wildcard: 'Wildcard',
};

function sourceLabel(source: DecisionStripSource, role?: DecisionRole): string | null {
  if (source === 'decision_session') return role ? ROLE_LABELS[role] : null;
  if (source === 'discovery') return 'WHY CRAVE SURFACED THIS';
  return null;
}

export function DecisionStrip({
  source,
  role,
  reason,
  fitLabel,
  confidenceLabel,
  practicalFacts,
  density = 'full',
  style,
}: DecisionStripProps) {
  const recommendationContext = source !== 'organic';
  const label = sourceLabel(source, role);
  const factParts = [
    practicalFacts?.distance,
    practicalFacts?.price,
    practicalFacts?.hours,
  ].filter((value): value is string => Boolean(value));

  if (!recommendationContext && factParts.length === 0) return null;
  if (
    recommendationContext &&
    !label &&
    !reason &&
    !fitLabel &&
    !confidenceLabel &&
    factParts.length === 0
  ) {
    return null;
  }

  return (
    <View style={[styles.container, density === 'compact' ? styles.compact : null, style]}>
      {label ? (
        <View style={styles.labelRow}>
          <Text style={styles.reasonLabel}>{label}</Text>
          {source === 'decision_session' && role === 'best_fit' ? (
            <Text style={styles.reasonLabel}> tonight</Text>
          ) : null}
        </View>
      ) : null}
      {recommendationContext && reason ? (
        <Text style={density === 'compact' ? styles.reasonCompact : styles.reason}>{reason}</Text>
      ) : null}
      {recommendationContext && fitLabel ? (
        <Text style={styles.fit}>{fitLabel}</Text>
      ) : null}
      {recommendationContext && confidenceLabel ? (
        <Text style={styles.confidence}>{confidenceLabel}</Text>
      ) : null}
      {factParts.length > 0 ? (
        <Text style={styles.facts}>{factParts.join('  ·  ')}</Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: Spacing.xs,
  },
  compact: {
    gap: Spacing.xs,
  },
  labelRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  reasonLabel: {
    ...Typography.micro,
    color: Colors.textSecondary,
    textTransform: 'uppercase',
  },
  reason: {
    ...Typography.body,
    color: Colors.text,
  },
  reasonCompact: {
    ...Typography.caption,
    color: Colors.text,
  },
  fit: {
    ...Typography.label,
    color: Colors.text,
  },
  confidence: {
    ...Typography.caption,
    color: Colors.textSecondary,
  },
  facts: {
    ...Typography.caption,
    color: Colors.textSecondary,
  },
});
