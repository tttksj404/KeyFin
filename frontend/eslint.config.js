// https://docs.expo.dev/guides/using-eslint/
const { defineConfig } = require("eslint/config");
const expoConfig = require("eslint-config-expo/flat");

module.exports = defineConfig([
  expoConfig,
  {
    ignores: ["dist/*", "node_modules/*", ".expo/*", "android/*", "ios/*", "lib/theme.ts"],
  },
  {
    // Jest 초기화 파일은 순수 JS 라 no-undef 가 살아 있어 `jest` 전역을 알려 줘야 한다 (테스트 .ts 는 typescript-eslint 가 no-undef 를 끈다)
    files: ["jest.setup.js"],
    languageOptions: { globals: { jest: "readonly" } },
  },
]);
