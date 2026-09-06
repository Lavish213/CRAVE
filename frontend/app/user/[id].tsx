// app/user/[id].tsx
//
// Someone else's profile: their ranked list plus a follow button. This is
// what the leaderboard and feed link into, and it's the reason a follow
// graph is worth having — you follow a person because you want to see
// their list.
import React, { useCallback, useRef, useState } from 'react';
import {
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
import { ErrorState } from '../../src/components/ErrorState';
import { SkeletonRowList } from '../../src/components/SkeletonCard';
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
import { withImageWidth, AVATAR_IMAGE_WIDTH } from '../../src/utils/imageUrl';

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
  // Distinct from notFound -- a network failure/timeout/5xx on the primary
  // profile fetch previously collapsed into the same "Profile not found"
  // EmptyState as a genuine 404, with no retry affordance. A transient
  // infrastructure failure is not the same product truth as "this account
  // doesn't exist, or its list is private," and unlike that EmptyState,
  // this is retryable.
  const [profileError, setProfileError] = useState(false);
  const [busy, setBusy] = useState(false);
  const [blockBusy, setBlockBusy] = useState(false);
  const [rankingsError, setRankingsError] = useState(false);
  const [relationshipError, setRelationshipError] = useState(false);

  const isSelf = !!me && me.id === id;

  // expo-router can reuse this screen instance across a param change (e.g.
  // tapping from one user's profile into another's, from a shared list) --
  // without a guard, a slow response for the *previous* id could resolve
  // after the new one's and silently repaint this screen with the wrong
  // person's profile/rankings/follow state.
  const loadGenerationRef = useRef(0);
  // Whose data this screen currently holds. `loading` previously only
  // ever flipped back to false (from the first load's `finally`) -- a
  // subsequent load() for a *different* id never set it back to true, so
  // between navigating to a new id and that id's fetch resolving, this
  // screen fell through the `if (loading)` skeleton gate entirely and
  // rendered the *previous* person's profile/rankings/follow state with
  // no loading indicator. The stale-response race above was already
  // guarded; this is the separate "nothing resets the visible state when
  // a fresh load starts" gap.
  const loadedForIdRef = useRef<string | null>(null);
  // Separately tracks *who was looking* the last time this loaded --
  // following/followsMe/blocked are relative to the viewer, not just the
  // profile being viewed. Viewing the same id="X" is not the same load
  // when the viewer switches from account A to account B: if both A and B
  // are non-self relative to X, `isSelf` (id + me.id alone) doesn't
  // change, so load()'s reference wouldn't change and this screen would
  // silently keep showing A's follow/block relationship with X under B's
  // session. me?.id is included in load()'s own deps below specifically
  // to force a fresh load whenever the viewer changes, independent of id.
  const loadedForViewerRef = useRef<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    const myGeneration = ++loadGenerationRef.current;
    const viewerId = me?.id ?? null;
    if (loadedForIdRef.current !== id || loadedForViewerRef.current !== viewerId) {
      setProfile(null);
      setRankings([]);
      setFollowing(false);
      setFollowsMe(false);
      setBlocked(false);
      setNotFound(false);
      setProfileError(false);
      setLoading(true);
    }
    // Marked as "attempted" here, before the fetch settles either way --
    // not only on success. This id/viewer pairing has been *addressed* by
    // this generation regardless of outcome; the render-time stale-gate
    // above only needs to force the skeleton until an attempt has been
    // made, not until one has succeeded. Setting this only on success
    // left the render-time gate permanently stuck on the skeleton after
    // any error (a 404 included) -- `loading` would still correctly flip
    // to false in `finally` below, but isStaleForCurrentIdentity would
    // never clear, so the component could never render past it.
    loadedForIdRef.current = id;
    loadedForViewerRef.current = viewerId;
    setRankingsError(false);
    setRelationshipError(false);
    try {
      const p = await fetchProfile(id);
      if (myGeneration !== loadGenerationRef.current) return;
      setProfile(p);

      const [r, status, blockStatus] = await Promise.all([
        fetchUserRankings(id).catch(() => null),
        isSelf
          ? Promise.resolve({ following: false, followed_by: false })
          : fetchFollowStatus(id).catch(() => null),
        isSelf
          ? Promise.resolve({ blocked: false })
          : fetchBlockStatus(id).catch(() => null),
      ]);
      if (myGeneration !== loadGenerationRef.current) return;
      if (r === null) {
        setRankingsError(true);
      } else {
        setRankings(r);
      }
      if (status === null || blockStatus === null) {
        setRelationshipError(true);
      } else {
        setFollowing(status.following);
        setFollowsMe(status.followed_by);
        setBlocked(blockStatus.blocked);
      }
    } catch (err: any) {
      if (myGeneration !== loadGenerationRef.current) return;
      // A 404 here is real product truth ("this account doesn't exist, or
      // its list is private" -- see get_public_profile's own is_public
      // gate). Anything else (network failure, timeout, 5xx) is an
      // infrastructure failure, not that truth, and must stay retryable
      // rather than collapsing into the same "not found" copy with no way
      // back -- this previously did exactly that, mislabeling a transient
      // failure as a nonexistent/private account.
      if (err?.response?.status === 404) setNotFound(true);
      else setProfileError(true);
    } finally {
      if (myGeneration === loadGenerationRef.current) setLoading(false);
    }
  }, [id, isSelf, me?.id]);

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

  // Derived at render time, not just from `loading` -- `loading` only
  // flips back to true from inside load(), which runs in an *effect*
  // (useFocusEffect), one render after `id`/`me` themselves have already
  // changed. Gating on the refs directly closes that one-render gap, same
  // fix as profile.tsx's identical `isStaleForCurrentUser`.
  const isStaleForCurrentIdentity =
    loadedForIdRef.current !== id || loadedForViewerRef.current !== (me?.id ?? null);
  if (loading || isStaleForCurrentIdentity) {
    // Matches the ranked-list-of-places shape this screen eventually
    // shows (RankedPlaceRow), same treatment as app/(tabs)/profile.tsx's
    // own ranked list -- this screen was still a plain ActivityIndicator,
    // inconsistent with every other list-shaped screen in the app.
    return (
      <View style={styles.content}>
        <SkeletonRowList count={5} />
      </View>
    );
  }

  if (notFound) {
    return (
      <EmptyState
        icon="person-outline"
        title="Profile not found"
        body="This account doesn't exist, or its list is private."
      />
    );
  }

  // profileError (an explicit non-404 failure) and the !profile fallback
  // (shouldn't happen given the two states above, but a defensive
  // catch-all) get the same retryable treatment -- neither is the "not
  // found" product truth above.
  if (profileError || !profile) {
    return <ErrorState message="Couldn't load this profile" onRetry={load} />;
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {!isSelf && !relationshipError ? (
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
          <Image
            source={withImageWidth(profile.avatar_url, AVATAR_IMAGE_WIDTH)}
            style={styles.avatar}
            contentFit="cover"
            cachePolicy="memory-disk"
          />
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
          <Ionicons name="ban-outline" size={20} color={Colors.textSecondary} />
          <Text style={styles.blockedNoticeText}>
            You've blocked @{profile.username}. Their activity is hidden from you.
          </Text>
          <TouchableOpacity onPress={doUnblock} disabled={blockBusy} accessibilityRole="button">
            <Text style={styles.unblockLink}>Unblock</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <>
          {relationshipError ? (
            <ErrorState
              message="Couldn't load relationship controls"
              onRetry={load}
            />
          ) : !isSelf ? (
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

          {rankingsError ? (
            <ErrorState message="Couldn't load ranked places" onRetry={load} />
          ) : (
            <>
              <Text style={styles.headline}>{rankedListHeadline(rankings.length)}</Text>

              {rankings.length > 0 && (
                <TouchableOpacity
                  style={styles.tasteProfileLink}
                  onPress={() => router.push(`/taste-profile/${id}`)}
                  accessibilityRole="button"
                  accessibilityLabel={isSelf ? 'View your Taste Profile' : `View ${profile.username}'s Taste Profile`}
                >
                  <Ionicons name="restaurant-outline" size={16} color={Colors.primary} />
                  <Text style={styles.tasteProfileLinkText}>
                    {isSelf ? 'Your Taste Profile' : 'Taste Profile'}
                  </Text>
                  <Ionicons name="chevron-forward" size={16} color={Colors.textSecondary} />
                </TouchableOpacity>
              )}

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
    color: Colors.textSecondary,
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
  username: { color: Colors.textSecondary, fontSize: 14, marginTop: 1 },
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
  tasteProfileLink: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    marginTop: Spacing.sm,
  },
  tasteProfileLinkText: { flex: 1, color: Colors.primary, fontSize: 14, fontWeight: '700' },
  emptyText: { color: Colors.textSecondary, fontSize: 14 },
  list: { gap: Spacing.sm },
});
