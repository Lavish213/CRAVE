import { StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Typography } from '../src/constants/colors';

export default function ActivityScreen() {
  return (
    <View style={styles.container}>
      <Ionicons name="notifications-outline" size={32} color={Colors.textSecondary} />
      <Text style={styles.title}>Activity</Text>
      <Text style={styles.body}>
        Follow requests, private reactions, and other actionable food events will appear here.
      </Text>
      <Text style={styles.hint}>
        Push notifications are optional. This inbox remains the in-app home for activity.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
    alignItems: 'center',
    justifyContent: 'center',
    padding: Spacing.xl,
    gap: Spacing.sm,
  },
  title: {
    ...Typography.title,
    color: Colors.text,
    textAlign: 'center',
  },
  body: {
    ...Typography.body,
    color: Colors.textSecondary,
    textAlign: 'center',
    maxWidth: 420,
  },
  hint: {
    ...Typography.caption,
    color: Colors.textSecondary,
    textAlign: 'center',
    maxWidth: 420,
    marginTop: Spacing.xs,
  },
});
