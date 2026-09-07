import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View, type ViewStyle } from 'react-native';
import { Colors, Radius, Spacing, Typography } from '../constants/colors';

export interface ActivityRowProps {
  title: string;
  body?: string | null;
  timestampLabel: string;
  unread?: boolean;
  onPress?: () => void;
  style?: ViewStyle;
  accessibilityLabel?: string;
}

export function ActivityRow({
  title,
  body,
  timestampLabel,
  unread = false,
  onPress,
  style,
  accessibilityLabel,
}: ActivityRowProps) {
  const content = (
    <View style={[styles.row, style]}>
      <View style={styles.indicatorColumn}>
        {unread ? <View style={styles.unreadDot} accessibilityElementsHidden /> : null}
      </View>
      <View style={styles.content}>
        <View style={styles.topLine}>
          <Text style={styles.title} numberOfLines={2}>{title}</Text>
          <Text style={styles.timestamp}>{timestampLabel}</Text>
        </View>
        {body ? <Text style={styles.body} numberOfLines={3}>{body}</Text> : null}
      </View>
    </View>
  );

  if (!onPress) return content;

  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.75}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? `${title}. ${timestampLabel}`}
    >
      {content}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  row: {
    minHeight: 64,
    flexDirection: 'row',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    backgroundColor: Colors.background,
  },
  indicatorColumn: {
    width: Spacing.md,
    paddingTop: Spacing.xs,
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: Radius.full,
    backgroundColor: Colors.primary,
  },
  content: {
    flex: 1,
    gap: Spacing.xs,
  },
  topLine: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Spacing.md,
  },
  title: {
    ...Typography.label,
    color: Colors.text,
    flex: 1,
  },
  timestamp: {
    ...Typography.micro,
    color: Colors.textSecondary,
  },
  body: {
    ...Typography.body,
    color: Colors.textSecondary,
  },
});
