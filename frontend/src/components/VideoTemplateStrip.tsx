// src/components/VideoTemplateStrip.tsx
//
// Horizontal shot-template picker for the record screen. Selecting one
// drives BeatCueOverlay's on-screen prompts during recording; recording
// with none selected is a valid, unguided path (templateId stays null).
import React from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Colors, Radius, Spacing } from '../constants/colors';
import type { VideoTemplate } from '../api/videos';

interface Props {
  templates: VideoTemplate[];
  selectedId: string | null;
  onSelect: (templateId: string | null) => void;
}

export function VideoTemplateStrip({ templates, selectedId, onSelect }: Props) {
  if (templates.length === 0) return null;

  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.container}
    >
      <TouchableOpacity
        style={[styles.chip, selectedId === null && styles.chipSelected]}
        onPress={() => onSelect(null)}
      >
        <Text style={[styles.chipText, selectedId === null && styles.chipTextSelected]}>
          Freestyle
        </Text>
      </TouchableOpacity>
      {templates.map((t) => {
        const selected = t.id === selectedId;
        return (
          <TouchableOpacity
            key={t.id}
            style={[styles.chip, selected && styles.chipSelected]}
            onPress={() => onSelect(t.id)}
          >
            <Text style={[styles.chipText, selected && styles.chipTextSelected]}>{t.name}</Text>
          </TouchableOpacity>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: Spacing.lg,
    gap: Spacing.sm,
  },
  chip: {
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
    borderRadius: Radius.pill,
    backgroundColor: Colors.surfaceElevated,
    borderWidth: 1,
    borderColor: Colors.border,
    marginRight: Spacing.sm,
  },
  chipSelected: {
    backgroundColor: Colors.primary,
    borderColor: Colors.primary,
  },
  chipText: {
    color: Colors.textSecondary,
    fontSize: 14,
    fontWeight: '600',
  },
  chipTextSelected: {
    color: Colors.background,
  },
});
