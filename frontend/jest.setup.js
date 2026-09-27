// Jest 전용 초기화. Reanimated 4 는 react-native-worklets 의 웹 구현으로 동작하도록
// package.json jest.resolver(react-native-worklets/jest/resolver)와 함께 쓴다.
require("react-native-reanimated").setUpTests();

// Lottie 는 네이티브 뷰라 Jest 에서 그릴 수 없다. 자리만 잡는 View 로 바꿔 둔다.
jest.mock("lottie-react-native", () => ({ __esModule: true, default: require("react-native").View }));

// Jest에서는 네이티브 SecureStore 대신 메모리 저장소를 사용한다.
jest.mock("expo-secure-store", () => {
  const storage = new Map();

  return {
    getItemAsync: jest.fn(async (key) => storage.get(key) ?? null),
    setItemAsync: jest.fn(async (key, value) => {
      storage.set(key, value);
    }),
    deleteItemAsync: jest.fn(async (key) => {
      storage.delete(key);
    }),
  };
});
