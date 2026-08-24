// src/components/BeatCueOverlay.tsx
//
// Timed on-screen prompt during recording (e.g. "hold plate steady" at
// t=0, "pull now" at t=4s) -- driven entirely by the selected template's
// beat_cues data (see backend/app/db/models/video_template.py), not
// hardcoded per template, so a new template needs a DB row, never a
// client change.
import React, { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Colors, Radius, Spacing } from '../constants/colors';
import type { VideoTemplate } from '../api/videos';

interface Props {
  template: VideoTemplate | null;
  elapsedMs: number;
}

function currentCue(template: VideoTemplate | null, elapsedSec: number): string | null {
  if (!template || template.beatCues.length === 0) return null;
  // Last cue whose timestamp has already passed -- cues are sparse
  // (a handful of seconds apart), so a linear scan is plenty fast.
  let active: string | null = null;
  for (const cue of template.beatCues) {
    if (cue.t <= elapsedSec) active = cue.cue;
  }
  return active;
}

export function BeatCueOverlay({ template, elapsedMs }: Props) {
  const [cue, setCue] = useState<string | null>(null);

  useEffect(() => {
    setCue(currentCue(template, elapsedMs / 1000));
  }, [template, elapsedMs]);

  if (!cue) return null;

  return (
    <View style={styles.container} pointerEvents="none">
      <Text style={styles.text}>{cue}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    top: '18%',
    alignSelf: 'center',
    backgroundColor: 'rgba(0,0,0,0.55)',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
    borderRadius: Radius.pill,
  },
  text: {
    color: Colors.text,
    fontSize: 16,
    fontWeight: '600',
  },
});
