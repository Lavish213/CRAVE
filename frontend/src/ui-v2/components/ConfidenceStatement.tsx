import React from 'react';
import { StyleSheet, View } from 'react-native';
import { uiSpace } from '../tokens';
import { CraveText } from '../primitives';

export type PersonalizationConfidence = 'strong' | 'moderate' | 'personalizationLearning';

export interface ConfidenceStatementProps {
  confidence: PersonalizationConfidence;
  compact?: boolean;
}

const statements: Record<PersonalizationConfidence, { copy: string; tone: 'positive' | 'secondary' | 'uncertain' }> = {
  strong: { copy: 'Strong fit for you', tone: 'positive' },
  moderate: { copy: 'Good fit based on what CRAVE knows', tone: 'secondary' },
  personalizationLearning: { copy: 'Still learning your taste here', tone: 'uncertain' },
};

export function ConfidenceStatement({ confidence, compact = false }: ConfidenceStatementProps) {
  const statement = statements[confidence];
  return (
    <View style={styles.container} accessibilityLabel={statement.copy}>
      <CraveText role={compact ? 'caption' : 'body'} tone={statement.tone}>{statement.copy}</CraveText>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: uiSpace.xs,
  },
});
