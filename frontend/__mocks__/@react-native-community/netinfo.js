// Jest can't load the real native module outside a device/simulator.
// Points at the package's own officially-documented jest mock.
module.exports = require('@react-native-community/netinfo/jest/netinfo-mock');
