// expo-secure-store is a native module and can't run under Jest outside a
// device/simulator. In-memory mock matching the real getItemAsync/
// setItemAsync/deleteItemAsync shape, following the same manual-mock
// convention as __mocks__/@react-native-async-storage/async-storage.js.
const store = new Map();

module.exports = {
  getItemAsync: jest.fn(async (key) => (store.has(key) ? store.get(key) : null)),
  setItemAsync: jest.fn(async (key, value) => {
    store.set(key, value);
  }),
  deleteItemAsync: jest.fn(async (key) => {
    store.delete(key);
  }),
  isAvailableAsync: jest.fn(async () => true),
  __reset: () => store.clear(),
};
