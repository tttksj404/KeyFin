import { useRouter } from "expo-router";
import { CircleAlert, Info } from "lucide-react-native";
import * as React from "react";
import { View } from "react-native";
import Animated from "react-native-reanimated";

import { Button } from "@/components/ui/button";
import { CoachRow } from "@/components/ui/coach-row";
import { Icon } from "@/components/ui/icon";
import { useIntroReveal } from "@/components/ui/intro-reveal";
import { Input } from "@/components/ui/input";
import { KeyboardAvoidingView } from "@/components/ui/keyboard-avoiding-view";
import { ScreenHeader } from "@/components/ui/screen-header";
import { Text } from "@/components/ui/text";
import { useConnectFinance } from "@/features/link/api/queries";
import { financeErrorMessage, isRetryableFinanceError } from "@/features/link/errors";
import { canSubmitFinanceEmail, FINANCE_EMAIL_MAX_LENGTH } from "@/features/link/model";
import { CHARACTER_FRAMES } from "@/features/room/assets";
import { cn } from "@/lib/utils";

/** 금융망 연결이 끝나야 후보 목록이 나오므로 곧바로 PAGE-04(계좌·카드 연결)로 보낸다 */
const NEXT_ROUTE = "/onboarding/asset-select";

// Pencil 금융망 이메일 · 캐릭터 대안 (PqGvX) · finance-email/error (B6jV5).
function FinanceEmailScreen() {
  const router = useRouter();
  const intro = useIntroReveal("finance-email");
  const connect = useConnectFinance();

  const [email, setEmail] = React.useState("");

  const errorMessage = connect.isError ? financeErrorMessage(connect.error) : null;
  const canRetry = connect.isError && isRetryableFinanceError(connect.error);
  const canSubmit = canSubmitFinanceEmail(email) && !connect.isPending;

  const handleSubmit = () => {
    if (!canSubmit) return;
    connect.mutate({ financeEmail: email.trim() }, { onSuccess: () => router.replace(NEXT_ROUTE) });
  };

  return (
    <KeyboardAvoidingView className="flex-1 bg-background">
      <Animated.View style={intro.revealStyle}>
        <ScreenHeader flat title="금융망 이메일 확인" />
      </Animated.View>

      <View className="flex-1 justify-between px-6 pb-8">
        <View className="gap-8">
          <CoachRow
            intro={intro}
            frames={CHARACTER_FRAMES.scan}
            message={"금융망 이메일로 계좌·카드를 찾아올게요.\nKeyFin 가입 이메일과 달라도 괜찮아요."}
          />

          <Animated.View style={intro.revealStyle}>
          <View className="gap-4">
            <View className="gap-1.5">
              <Text className="text-caption text-card-foreground">금융망 이메일</Text>
              <Input
                className={cn("h-input rounded-lg", errorMessage !== null && "border-destructive")}
                value={email}
                onChangeText={setEmail}
                placeholder="finance@qwer.com"
                keyboardType="email-address"
                autoCapitalize="none"
                autoCorrect={false}
                maxLength={FINANCE_EMAIL_MAX_LENGTH}
                editable={!connect.isPending}
                accessibilityLabel="금융망 이메일"
                returnKeyType="done"
                onSubmitEditing={handleSubmit}
              />
              {errorMessage === null ? null : (
                <View className="flex-row items-center gap-1.5" accessibilityLiveRegion="polite">
                  <Icon as={CircleAlert} size={16} className="text-destructive" />
                  <Text className="flex-1 text-body-sm text-destructive">
                    {canRetry ? errorMessage : `${errorMessage} 다른 이메일을 입력해 주세요.`}
                  </Text>
                </View>
              )}
            </View>

            <View className="flex-row items-center gap-2 rounded-lg bg-info-muted p-3.5">
              <Icon as={Info} size={16} className="text-info" />
              <Text className="flex-1 text-caption text-foreground">회원가입에 쓴 이메일과 다를 수 있어요.</Text>
            </View>
          </View>
          </Animated.View>
        </View>

        <Animated.View style={intro.revealStyle}>
        <Button
          size="lg"
          className="h-button-lg rounded-lg"
          onPress={handleSubmit}
          disabled={!canSubmit}
          accessibilityLabel="연결하기"
        >
          <Text>{connect.isPending ? "연결하는 중…" : "연결하기"}</Text>
        </Button>
        </Animated.View>
      </View>
    </KeyboardAvoidingView>
  );
}

export { FinanceEmailScreen };
