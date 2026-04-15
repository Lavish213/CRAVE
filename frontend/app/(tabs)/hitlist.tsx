// app/(tabs)/hitlist.tsx
import React, { useEffect, useState } from 'react';
import {
  FlatList,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { useHitlistStore } from '../../src/stores/hitlistStore';
import { useToast } from '../../src/hooks/useToast';
import { Colors } from '../../src/constants/colors';
import { PlaceCardCompact } from '../../src/components/PlaceCardCompact';
import { EmptyState } from '../../src/components/EmptyState';
import { getCraveItems, CraveItem } from '../../src/api/crave';

export default function HitlistScreen() {
  const router = useRouter();
  const { saves, removeSave } = useHitlistStore();
  const toast = useToast((s) => s.show);
  const [craves, setCraves] = useState<CraveItem[]>([]);

  useEffect(() => {
    getCraveItems().then(setCraves).catch(() => {});
  }, []);

  if (saves.length === 0 && craves.length === 0) {
    return (
      <EmptyState
        icon="bookmark-outline"
        title="Your Hitlist is empty"
        body="Tap the bookmark on any place to save it here"
      />
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={saves}
        keyExtractor={(p) => p.id}
        renderItem={({ item }) => (
          <PlaceCardCompact
            place={item}
            onPress={() => router.push(`/place/${item.id}`)}
            rightAction={
              <TouchableOpacity
                onPress={() => {
                  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
                  removeSave(item.id);
                  toast('Removed from Hitlist');
                }}
                style={styles.removeBtn}
                hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                accessibilityLabel={`Remove ${item.name} from hitlist`}
                accessibilityRole="button"
              >
                <Ionicons name="close" size={18} color={Colors.textMuted} />
              </TouchableOpacity>
            }
          />
        )}
        contentContainerStyle={styles.list}
        ListHeaderComponent={
          saves.length > 0 ? (
            <Text style={styles.countLabel}>
              {saves.length} {saves.length === 1 ? 'place' : 'places'} saved
            </Text>
          ) : null
        }
        ListFooterComponent={
          craves.length > 0 ? (
            <View style={styles.cravesSection}>
              <Text style={styles.craveSectionLabel}>CRAVES</Text>
              {craves.map((item) => (
                <View key={item.id} style={styles.craveRow}>
                  <View style={styles.craveMeta}>
                    <Text style={styles.craveName} numberOfLines={1}>
                      {item.parsed_place_name ?? item.url}
                    </Text>
                    <Text style={[styles.craveStatus, {
                      color: item.matched_place_id ? Colors.success : Colors.textMuted
                    }]}>
                      {item.matched_place_id ? 'Matched' : 'Pending match'}
                    </Text>
                  </View>
                  {item.matched_place_id && (
                    <TouchableOpacity
                      style={styles.craveOpenBtn}
                      onPress={() => router.push(`/place/${item.matched_place_id!}`)}
                      accessibilityRole="button"
                      accessibilityLabel={`Open matched place for ${item.parsed_place_name ?? 'this place'}`}
                    >
                      <Ionicons name="arrow-forward" size={16} color={Colors.primary} />
                    </TouchableOpacity>
                  )}
                </View>
              ))}
            </View>
          ) : null
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  list: { padding: 12, gap: 8, paddingBottom: 32 },
  countLabel: {
    color: Colors.textMuted,
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    paddingBottom: 10,
  },
  removeBtn: {
    padding: 8,
    minWidth: 44,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cravesSection: { paddingTop: 16, paddingBottom: 8 },
  craveSectionLabel: {
    color: Colors.textMuted,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    paddingBottom: 10,
  },
  craveRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    backgroundColor: Colors.surface,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: 8,
  },
  craveMeta: { flex: 1 },
  craveName: { color: Colors.text, fontSize: 14, fontWeight: '600' },
  craveStatus: { fontSize: 12, marginTop: 2 },
  craveOpenBtn: { padding: 8, minWidth: 44, minHeight: 44, alignItems: 'center', justifyContent: 'center' },
});
