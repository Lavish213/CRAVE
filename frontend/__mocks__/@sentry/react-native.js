// Jest can't load Sentry's real native modules outside a device/simulator,
// and no test should ever actually attempt to reach Sentry. Same convention
// as this repo's other node_modules manual mocks (react-native-maps,
// @react-native-async-storage) -- Jest picks this up automatically for any
// `require('@sentry/react-native')`, no explicit jest.mock() call needed.
module.exports = {
  init: jest.fn(),
  wrap: (component) => component,
  captureException: jest.fn(),
  captureMessage: jest.fn(),
  setTag: jest.fn(),
  setUser: jest.fn(),
  addBreadcrumb: jest.fn(),
};
