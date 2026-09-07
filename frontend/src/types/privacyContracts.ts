export type PostVisibility = 'private' | 'following' | 'public';
export type NotificationCategory =
  | 'rank_reminders'
  | 'shared_craves'
  | 'follow_requests'
  | 'reservation_events'
  | 'saved_place_updates'
  | 'taste_match_updates'
  | 'followed_person_posts'
  | 'private_reaction_summary';

export type PrivacyMutation =
  | { type: 'set_profile_discoverable'; value: boolean }
  | { type: 'set_private_account'; value: boolean }
  | { type: 'set_default_post_visibility'; value: PostVisibility }
  | { type: 'set_personalization_paused'; value: boolean }
  | { type: 'reset_current_recommendations' }
  | { type: 'reset_inferred_taste' }
  | { type: 'set_notification_category'; category: NotificationCategory; enabled: boolean }
  | { type: 'mute_user'; userId: string; muted: boolean }
  | { type: 'set_taste_influence_from_user'; userId: string; enabled: boolean }
  | { type: 'block_user'; userId: string; blocked: boolean };

export type PrivacyAxis = 'visibility' | 'recommendation_influence' | 'factual_retention';

/**
 * The three privacy axes are deliberately independent. This helper exists so
 * UI/API code cannot treat a visibility mutation as a deletion or taste reset.
 */
export function affectedPrivacyAxes(mutation: PrivacyMutation): readonly PrivacyAxis[] {
  switch (mutation.type) {
    case 'set_profile_discoverable':
    case 'set_private_account':
    case 'set_default_post_visibility':
    case 'block_user':
      return ['visibility'];
    case 'set_personalization_paused':
    case 'reset_current_recommendations':
    case 'reset_inferred_taste':
    case 'set_taste_influence_from_user':
      return ['recommendation_influence'];
    case 'set_notification_category':
    case 'mute_user':
      return [];
  }
}
