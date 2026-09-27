import { KeyboardAvoidingView as RNKeyboardAvoidingView, type KeyboardAvoidingViewProps } from "react-native";

/**
 * 키패드가 올라오면 내용을 그만큼 밀어 올리는 래퍼. 입력이 있는 화면(로그인·회원가입·금융망 이메일·고정지출·설정·예산 비상금·코칭 대화)과
 * 바텀시트가 쓴다.
 *
 * Android 는 예전엔 `adjustResize` 가 창 자체를 줄여 줘서 `behavior` 를 비워 두면 됐지만, Expo SDK 54 부터 Android 가 항상 edge-to-edge 라
 * 창이 줄어들지 않는다 — 그래서 APK 에서 키패드가 로그인·금액·채팅 입력을 그대로 덮었다(2026-09-22 사용자 보고).
 * iOS·Android 모두 `padding` 으로 직접 밀어 올린다. 내비게이터 헤더가 없어(headerShown false) 기본 offset 은 0 이다.
 */
function KeyboardAvoidingView({ behavior = "padding", ...props }: KeyboardAvoidingViewProps) {
  return <RNKeyboardAvoidingView behavior={behavior} {...props} />;
}

export { KeyboardAvoidingView };
