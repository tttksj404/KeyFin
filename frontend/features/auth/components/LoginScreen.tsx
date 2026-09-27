import { useLocalSearchParams, useRouter } from "expo-router";
import { CircleAlert } from "lucide-react-native";
import * as React from "react";
import { Image, Pressable, ScrollView, View } from "react-native";
import Animated from "react-native-reanimated";

import { isMocked } from "@/api/client";
import { MOCK_LOGIN_EMAIL, MOCK_PASSWORD } from "@/api/mocks/auth";
import { Button } from "@/components/ui/button";
import { Floating } from "@/components/ui/floating";
import { Sprite } from "@/components/ui/sprite";
import { Icon } from "@/components/ui/icon";
import { KeyboardAvoidingView } from "@/components/ui/keyboard-avoiding-view";
import { useIntroReveal } from "@/components/ui/intro-reveal";
import { Input } from "@/components/ui/input";
import { Text } from "@/components/ui/text";
import { useLogin } from "@/features/auth/api/queries";
import { authErrorMessage } from "@/features/auth/errors";
import { canSubmitLogin, parseReturnTo } from "@/features/auth/model";
import { CHARACTER_FRAMES } from "@/features/room/assets";
import { cn } from "@/lib/utils";

/** Pencil 로그인 · 캐릭터 대안(QmtGU) 의 Main Logo 1 에서 태그라인을 뺀 아이콘+워드마크를 3배로 내보낸 이미지 */
const WORDMARK = require("@/assets/brand/keyfin-wordmark.png");

/** NativeWind className 은 RN Image 에 적용되지 않아 크기만 style 로 준다. 시안 117×27, 캐릭터 150×210 */
const WORDMARK_STYLE = { width: 117, height: 27 } as const;
const CHARACTER_STYLE = { width: 150, height: 210 } as const;

const SIGNUP_ROUTE = "/(auth)/signup";

/**
 * 개발 빌드에서 auth 가 목이면 목 계정을 미리 채운다 — 서버 없이 화면을 볼 때마다 치는 수고를 던다(사용자 요청 2026-09-15).
 * 배포 빌드(__DEV__ false)나 실서버 auth 에서는 절대 채우지 않는다.
 */
const MOCK_PREFILL = __DEV__ && isMocked("auth") ? { email: MOCK_LOGIN_EMAIL, password: MOCK_PASSWORD } : null;

// Pencil 로그인 · 캐릭터 대안 (QmtGU) · login/error (JF0Db) · login/pending (bG1FL).
function LoginScreen() {
  const router = useRouter();
  const login = useLogin();
  const intro = useIntroReveal("login");

  // 가입 직후 돌아오면 방금 만든 이메일을 채워 두고 안내를 한 줄 보여준다.
  const { signedUpEmail, returnTo } = useLocalSearchParams<{ signedUpEmail?: string; returnTo?: string }>();
  const [email, setEmail] = React.useState(signedUpEmail ?? MOCK_PREFILL?.email ?? "");
  const [password, setPassword] = React.useState(signedUpEmail === undefined ? (MOCK_PREFILL?.password ?? "") : "");

  const errorMessage = login.isError ? authErrorMessage(login.error) : null;
  const canSubmit = canSubmitLogin(email, password) && !login.isPending;

  const handleSubmit = () => {
    if (!canSubmit) return;
    // 온보딩 완료 여부로 분기하는 자리. 판정 기준이 미정이고 PAGE-03~06 이 없어 지금은 홈으로 보낸다. (TBD)
    // 푸시·딥링크로 들어왔다 로그인한 경우 원래 보려던 화면으로 돌아간다 (규칙 50).
    login.mutate({ email: email.trim(), password }, { onSuccess: () => router.replace(parseReturnTo(returnTo)) });
  };

  return (
    <KeyboardAvoidingView className="flex-1 bg-background">
      <ScrollView className="flex-1" contentContainerClassName="gap-7 px-6 pt-4" keyboardShouldPersistTaps="handled">
        <Animated.View style={intro.revealStyle}>
          <Image source={WORDMARK} style={WORDMARK_STYLE} resizeMode="contain" accessibilityRole="image" accessibilityLabel="KeyFin" />
        </Animated.View>

        <View className="items-center gap-5">
          <Animated.View ref={intro.characterRef} onLayout={intro.onCharacterLayout} style={intro.characterStyle}>
            <Floating>
              <Sprite frames={CHARACTER_FRAMES.wave} style={CHARACTER_STYLE} />
            </Floating>
          </Animated.View>
          <Animated.View style={intro.revealStyle}>
            <View className="items-center gap-1.5">
              <Text className="text-h1 text-foreground" accessibilityRole="header">
                안녕하세요!
              </Text>
              <Text className="text-body-sm text-card-foreground">로그인하면 방으로 바로 들어가요</Text>
            </View>
          </Animated.View>
        </View>

        <Animated.View style={intro.revealStyle}>
        <View className="gap-7">
        {signedUpEmail === undefined ? null : (
          <View className="rounded-lg bg-positive-muted px-4 py-3" accessibilityLiveRegion="polite">
            <Text className="text-body-sm text-foreground">가입이 완료됐어요. 로그인해 주세요.</Text>
          </View>
        )}
        {MOCK_PREFILL !== null && signedUpEmail === undefined ? (
          <View className="rounded-lg bg-muted px-4 py-3">
            <Text className="text-left text-body-sm text-card-foreground">{"개발용 목 계정이 채워져 있어요.\n로그인만 누르면 돼요."}</Text>
          </View>
        ) : null}

        <View className="gap-4">
          <Field label="이메일">
            <Input
              className={cn("h-input rounded-lg", errorMessage !== null && "border-destructive")}
              value={email}
              onChangeText={setEmail}
              placeholder="you@example.com"
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
              autoComplete="email"
              textContentType="emailAddress"
              editable={!login.isPending}
              accessibilityLabel="이메일"
              returnKeyType="next"
            />
          </Field>

          <Field label="비밀번호">
            <Input
              className={cn("h-input rounded-lg", errorMessage !== null && "border-destructive")}
              value={password}
              onChangeText={setPassword}
              placeholder="비밀번호"
              secureTextEntry
              autoCapitalize="none"
              autoComplete="current-password"
              textContentType="password"
              editable={!login.isPending}
              accessibilityLabel="비밀번호"
              returnKeyType="done"
              onSubmitEditing={handleSubmit}
            />
          </Field>

          {errorMessage === null ? null : (
            <View className="flex-row items-center gap-1.5" accessibilityLiveRegion="polite">
              <Icon as={CircleAlert} size={16} className="text-destructive" />
              <Text className="flex-1 text-body-sm text-destructive">{errorMessage}</Text>
            </View>
          )}
        </View>
        </View>
        </Animated.View>
      </ScrollView>

      <Animated.View style={intro.revealStyle}>
      <View className="gap-4 px-6 pb-8 pt-4">
        <Button
          size="lg"
          className="h-button-lg rounded-lg"
          onPress={handleSubmit}
          disabled={!canSubmit}
          accessibilityLabel="로그인"
        >
          <Text>{login.isPending ? "로그인 중…" : "로그인"}</Text>
        </Button>

        <View className="flex-row items-center justify-center gap-1.5">
          <Text className="text-body-sm text-card-foreground">계정이 없으신가요?</Text>
          <Pressable
            accessibilityRole="link"
            accessibilityLabel="회원가입"
            hitSlop={10}
            onPress={() => router.push(SIGNUP_ROUTE)}
          >
            <Text className="text-label text-primary">회원가입</Text>
          </Pressable>
        </View>
      </View>
      </Animated.View>
    </KeyboardAvoidingView>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View className="gap-1.5">
      <Text className="text-caption text-card-foreground">{label}</Text>
      {children}
    </View>
  );
}

export { LoginScreen };
