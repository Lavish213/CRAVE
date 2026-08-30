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
});
