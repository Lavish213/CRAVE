import { affectedPrivacyAxes, type PrivacyMutation } from './privacyContracts';

describe('privacy mutation contracts', () => {
  it.each([
    [{ type: 'set_profile_discoverable', value: false }, ['visibility']],
    [{ type: 'set_personalization_paused', value: true }, ['recommendation_influence']],
    [{ type: 'reset_inferred_taste' }, ['recommendation_influence']],
    [{ type: 'set_notification_category', category: 'rank_reminders', enabled: false }, []],
  ] as const)('keeps %o on its explicit privacy axes', (mutation, expected) => {
    expect(affectedPrivacyAxes(mutation as PrivacyMutation)).toEqual(expected);
  });

  it('never treats a personalization reset as factual deletion', () => {
    expect(affectedPrivacyAxes({ type: 'reset_inferred_taste' })).not.toContain('factual_retention');
    expect(affectedPrivacyAxes({ type: 'reset_current_recommendations' })).not.toContain('factual_retention');
  });
});
