// Jest can't load the real native module outside a device/simulator.
// Points at the package's own officially-documented jest mock
// (https://react-native-async-storage.github.io/async-storage/docs/advanced/jest).
module.exports = require('@react-native-async-storage/async-storage/jest/async-storage-mock');
