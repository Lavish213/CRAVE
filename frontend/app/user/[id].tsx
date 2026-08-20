// app/user/[id].tsx
//
// Someone else's profile: their ranked list plus a follow button. This is
// what the leaderboard and feed link into, and it's the reason a follow
// graph is worth having — you follow a person because you want to see
// their list.
import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';

import { Colors, Radius, Spacing } from '../../src/constants/colors';
import { EmptyState } from '../../src/components/EmptyState';
import { RankedPlaceRow } from '../../src/components/RankedPlaceRow';
import { useAuthStore } from '../../src/stores/authStore';
import {
  Profile,
  RankedPlace,
  blockUser,
  fetchBlockStatus,
  fetchFollowStatus,
  fetchProfile,
  fetchUserRankings,
  followUser,
  unblockUser,
  unfollowUser,
} from '../../src/api/social';
import { rankedListHeadline } from '../../src/utils/rankScore';

export default function UserProfileScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const me = useAuthStore((s) => s.user);

  const [profile, setProfile] = useState<Profile | null>(null);
  const [rankings, setRankings] = useState<RankedPlace[]>([]);
  const [following, setFollowing] = useState(false);
  const [followsMe, setFollowsMe] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [busy, setBusy] = useState(false);
  const [blockBusy, setBlockBusy] = useState(false);

  const isSelf = !!me && me.id === id;

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const p = await fetchProfile(id);
      setProfile(p);

      const [r, status, blockStatus] = await Promise.all([
        fetchUserRankings(id).catch(() => [] as RankedPlace[]),
        isSelf
          ? Promise.resolve({ following: false, followed_by: false })
          : fetchFollowStatus(id).catch(() => ({ following: false, followed_by: false })),
        isSelf
          ? Promise.resolve({ blocked: false })
          : fetchBlockStatus(id).catch(() => ({ blocked: false })),
      ]);
      setRankings(r);
      setFollowing(status.following);
      setFollowsMe(status.followed_by);
      setBlocked(blockStatus.blocked);
    } catch (err: any) {
      if (err?.response?.status === 404) setNotFound(true);
    } finally {
      setLoading(false);
    }
  }, [id, isSelf]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const toggleFollow = async () => {
    if (!id || busy || isSelf) return;
    setBusy(true);
    // Optimistic — the button is the whole interaction, so it must respond
    // instantly; reverted below if the request fails.
    const previous = following;
    setFollowing(!previous);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    try {
      if (previous) {
        await unfollowUser(id);
      } else {
        await followUser(id);
      }
    } catch {
      setFollowing(previous);
    } finally {
      setBusy(false);
    }
  };

  const doBlock = async () => {
    if (!id || blockBusy) return;
    setBlockBusy(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    try {
      await blockUser(id);
      // Blocking severs any existing follow both ways server-side —
      // reflect that immediately rather than waiting on a reload.
      setBlocked(true);
      setFollowing(false);
      setFollowsMe(false);
    } catch {
      Alert.alert("Couldn't block", 'Something went wrong. Try again.');
    } finally {
      setBlockBusy(false);
    }
  };

  const doUnblock = async () => {
    if (!id || blockBusy) return;
    setBlockBusy(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    try {
      await unblockUser(id);
      setBlocked(false);
    } catch {
      Alert.alert("Couldn't unblock", 'Something went wrong. Try again.');
    } finally {
      setBlockBusy(false);
    }
  };

  const showOptions = () => {
    if (!profile) return;
    if (blocked) {
      Alert.alert(profile.username, undefined, [
        { text: 'Unblock', onPress: doUnblock },
        { text: 'Cancel', style: 'cancel' },
      ]);
      return;
    }
    Alert.alert(profile.username, undefined, [
      {
        text: 'Block user',
        style: 'destructive',
        onPress: () =>
          Alert.alert(
            `Block @${profile.username}?`,
            "You won't see their activity and they won't see yours. This also removes any follow between you.",
            [
              { text: 'Cancel', style: 'cancel' },
              { text: 'Block', style: 'destructive', onPress: doBlock },
            ],
          ),
      },
      { text: 'Cancel', style: 'cancel' },
    ]);
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator color={Colors.primary} size="large" />
      </View>
    );
  }

  if (notFound || !profile) {
    return (
      <EmptyState
        icon="person-outline"
        title="Profile not found"
        body="This account doesn't exist, or its list is private."
      />
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {!isSelf ? (
        <TouchableOpacity
          style={styles.optionsBtn}
          onPress={showOptions}
          accessibilityRole="button"
          accessibilityLabel="More options"
        >
          <Ionicons name="ellipsis-horizontal" size={20} color={Colors.textSecondary} />
        </TouchableOpacity>
      ) : null}

      <View style={styles.header}>
        {profile.avatar_url ? (
          <Image source={profile.avatar_url} style={styles.avatar} contentFit="cover" />
        ) : (
          <View style={[styles.avatar, styles.avatarFallback]}>
            <Text style={styles.avatarInitial}>
              {(profile.display_name ?? profile.username).charAt(0).toUpperCase()}
            </Text>
          </View>
        )}

        <View style={styles.headerMeta}>
          <Text style={styles.displayName} numberOfLines={1}>
            {profile.display_name ?? profile.username}
          </Text>
          <Text style={styles.username}>@{profile.username}</Text>
          {followsMe && !isSelf ? <Text style={styles.followsYou}>Follows you</Text> : null}
        </View>
      </View>

      {profile.bio ? <Text style={styles.bio}>{profile.bio}</Text> : null}

      {blocked ? (
        <View style={styles.blockedNotice}>
          <Ionicons name="ban-outline" size={20} color={Colors.textMuted} />
          <Text style={styles.blockedNoticeText}>
            You've blocked @{profile.username}. Their activity is hidden from you.
          </Text>
          <TouchableOpacity onPress={doUnblock} disabled={blockBusy} accessibilityRole="button">
            <Text style={styles.unblockLink}>Unblock</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <>
          {!isSelf ? (
            <TouchableOpacity
              style={[styles.followBtn, following ? styles.followingBtn : null]}
              onPress={toggleFollow}
              disabled={busy}
              accessibilityRole="button"
              accessibilityState={{ selected: following }}
              accessibilityLabel={following ? `Unfollow ${profile.username}` : `Follow ${profile.username}`}
            >
              <Ionicons
                name={following ? 'checkmark' : 'add'}
                size={17}
                color={following ? Colors.text : '#FFFFFF'}
              />
              <Text style={[styles.followBtnText, following ? styles.followingBtnText : null]}>
                {following ? 'Following' : 'Follow'}
              </Text>
            </TouchableOpacity>
          ) : null}

          <Text style={styles.headline}>{rankedListHeadline(rankings.length)}</Text>

          {rankings.length === 0 ? (
            <Text style={styles.emptyText}>
              {isSelf ? "You haven't" : `@${profile.username} hasn't`} ranked anything yet.
            </Text>
          ) : (
            <View style={styles.list}>
              {rankings.map((r, i) => (
                <RankedPlaceRow
                  key={r.place_id}
                  position={i + 1}
                  name={r.name ?? 'Unknown place'}
                  imageUrl={r.primary_image_url}
                  score={r.rank_score}
                  tier={r.tier}
                  note={r.note}
                  onPress={() => router.push(`/place/${r.place_id}`)}
                />
              ))}
            </View>
          )}
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  content: { padding: Spacing.lg, paddingBottom: Spacing.xxl, gap: Spacing.md },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.background,
  },
  optionsBtn: { alignSelf: 'flex-end', padding: Spacing.xs },
  blockedNotice: {
    alignItems: 'center',
    gap: Spacing.sm,
    paddingVertical: Spacing.lg,
    borderRadius: Radius.card,
    backgroundColor: Colors.surfaceElevated,
  },
  blockedNoticeText: {
    color: Colors.textMuted,
    fontSize: 13,
    textAlign: 'center',
    paddingHorizontal: Spacing.lg,
  },
  unblockLink: { color: Colors.primary, fontSize: 14, fontWeight: '700' },
  header: { flexDirection: 'row', alignItems: 'center', gap: Spacing.md },
  avatar: { width: 64, height: 64, borderRadius: Radius.full, backgroundColor: Colors.surfaceElevated },
  avatarFallback: { alignItems: 'center', justifyContent: 'center' },
  avatarInitial: { color: Colors.text, fontSize: 26, fontWeight: '800' },
  headerMeta: { flex: 1 },
  displayName: { color: Colors.text, fontSize: 20, fontWeight: '800' },
  username: { color: Colors.textMuted, fontSize: 14, marginTop: 1 },
  followsYou: { color: Colors.textSecondary, fontSize: 12, marginTop: Spacing.xs, fontWeight: '600' },
  bio: { color: Colors.textSecondary, fontSize: 14, lineHeight: 20 },
  followBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    backgroundColor: Colors.primary,
    borderRadius: Radius.pill,
    paddingVertical: 12,
    minHeight: 46,
    borderWidth: 1,
    borderColor: Colors.primary,
  },
  followingBtn: { backgroundColor: 'transparent', borderColor: Colors.border },
  followBtnText: { color: '#FFFFFF', fontSize: 15, fontWeight: '800' },
  followingBtnText: { color: Colors.text },
  headline: { color: Colors.text, fontSize: 16, fontWeight: '700', marginTop: Spacing.sm },
  emptyText: { color: Colors.textMuted, fontSize: 14 },
  list: { gap: Spacing.sm },
});
