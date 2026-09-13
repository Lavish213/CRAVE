import appConfig from '../../app.json';

describe('native app configuration', () => {
  it('declares the iOS background modes required by the notification delegates', () => {
    expect(appConfig.expo.ios.infoPlist.UIBackgroundModes).toEqual(
      expect.arrayContaining(['fetch', 'remote-notification']),
    );

    const notificationsPlugin = appConfig.expo.plugins.find(
      (plugin) => Array.isArray(plugin) && plugin[0] === 'expo-notifications',
    );

    expect(notificationsPlugin).toEqual([
      'expo-notifications',
      expect.objectContaining({ enableBackgroundRemoteNotifications: true }),
    ]);
  });

  it('registers crave.app universal-link destinations on both native platforms', () => {
    expect(appConfig.expo.ios.associatedDomains).toContain('applinks:crave.app');
    expect(appConfig.expo.android.intentFilters).toEqual(expect.arrayContaining([
      expect.objectContaining({
        action: 'VIEW',
        autoVerify: true,
        category: expect.arrayContaining(['BROWSABLE', 'DEFAULT']),
      }),
    ]));
  });
});
