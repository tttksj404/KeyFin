import { useRouter } from "expo-router";
import { Circle, CircleCheckBig } from "lucide-react-native";
import * as React from "react";
import { Pressable, View } from "react-native";
import Animated from "react-native-reanimated";

import { Button } from "@/components/ui/button";
import { CoachRow } from "@/components/ui/coach-row";
import { Icon } from "@/components/ui/icon";
import { useIntroReveal } from "@/components/ui/intro-reveal";
import { Screen, ScreenScrollView } from "@/components/ui/screen";
import { ScreenHeader } from "@/components/ui/screen-header";
import { Text } from "@/components/ui/text";
import { canAgreeToTerms, HOME_ROUTE, TERMS_ITEMS } from "@/features/auth/model";
import { useAuthStore } from "@/features/auth/store";
import { CHARACTER_FRAMES } from "@/features/room/assets";
import { saveTermsAgreed } from "@/lib/session-storage";
import { cn } from "@/lib/utils";

/**
 * 약관 다음 단계는 홈 게이트(app/(app)/(tabs)/_layout)가 정한다. 금융망 미연결이면 금융망 이메일(PAGE-03B)로,
 * 이미 연결된 계정(새 기기·웹 새로고침으로 동의 기록만 없는 경우)이면 홈으로 간다.
 */
const NEXT_ROUTE = HOME_ROUTE;

const CLAUSES = [
  {
    title: "제1조 (목적)",
    body: "이 약관은 KeyFin 및 관련 자산 연동 서비스를 이용함에 있어 회사와 회원의 권리·의무를 정합니다.",
  },
  {
    title: "제2조 (개인정보 수집 및 이용)",
    body: "회사는 자산 연동과 예산 리포트 제공을 위해 필요 최소한의 개인정보를 수집하며 수집 시 목적을 고지합니다.",
  },
  {
    title: "제3조 (서비스 제공 및 변경)",
    body: "서비스는 24시간 제공을 원칙으로 하나 점검 등 불가피한 사유가 있으면 사전 고지 후 중단될 수 있습니다.",
  },
];

// Pencil 약관 동의 · 캐릭터 대안 (f0WyT). 서버 호출이 없어 동의는 기기에만 남긴다.
function TermsScreen() {
  const router = useRouter();
  const intro = useIntroReveal("terms");
  const user = useAuthStore((state) => state.user);
  const agreeToTerms = useAuthStore((state) => state.agreeToTerms);

  const [checkedIds, setCheckedIds] = React.useState<string[]>([]);
  const allChecked = checkedIds.length === TERMS_ITEMS.length;
  const canContinue = canAgreeToTerms(checkedIds);

  const toggle = (id: string) => {
    setCheckedIds((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));
  };

  const toggleAll = () => {
    setCheckedIds(allChecked ? [] : TERMS_ITEMS.map((item) => item.id));
  };

  const handleContinue = async () => {
    if (!canContinue || user === null) return;
    await saveTermsAgreed(user.id);
    agreeToTerms();
    router.replace(NEXT_ROUTE);
  };

  return (
    <Screen>
      <Animated.View style={intro.revealStyle}>
        <ScreenHeader flat title="약관에 동의해 주세요" />
      </Animated.View>

      <ScreenScrollView className="flex-1" contentContainerClassName="gap-5 px-6">
        <CoachRow
          intro={intro}
          frames={CHARACTER_FRAMES.phone}
          message={"약관은 제가 미리 읽어 봤어요.\n필수 2개만 체크하면 바로 시작할 수 있어요."}
        />

        <Animated.View style={intro.revealStyle}>
        <View className="gap-5">
        <View className="gap-2.5 rounded-lg bg-muted p-4">
          {CLAUSES.map((clause) => (
            <View key={clause.title} className="gap-1">
              <Text className="text-label text-foreground">{clause.title}</Text>
              <Text className="text-caption text-card-foreground">{clause.body}</Text>
            </View>
          ))}
        </View>

        <View className="gap-3.5">
          <Pressable
            className="flex-row items-center gap-2.5 rounded-lg bg-card px-4 py-3.5 shadow shadow-black/10 dark:border dark:border-border dark:shadow-none"
            accessibilityRole="checkbox"
            accessibilityLabel="전체 동의"
            accessibilityState={{ checked: allChecked }}
            onPress={toggleAll}
          >
            <CheckMark checked={allChecked} />
            <Text className="text-h3 text-foreground">전체 동의</Text>
          </Pressable>

          <View className="gap-3 px-1">
            {TERMS_ITEMS.map((item) => {
              const checked = checkedIds.includes(item.id);
              return (
                <Pressable
                  key={item.id}
                  className="flex-row items-center gap-2.5"
                  accessibilityRole="checkbox"
                  accessibilityLabel={item.label}
                  accessibilityState={{ checked }}
                  onPress={() => toggle(item.id)}
                  hitSlop={6}
                >
                  <CheckMark checked={checked} />
                  <Text className={cn("flex-1 text-body-sm", checked ? "text-foreground" : "text-card-foreground")}>
                    {item.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>
        </View>
        </Animated.View>
      </ScreenScrollView>

      <Animated.View style={intro.revealStyle}>
      <View className="px-6 pb-8 pt-3">
        <Button
          size="lg"
          className="h-button-lg rounded-lg"
          onPress={handleContinue}
          disabled={!canContinue}
          accessibilityLabel="동의하고 계속하기"
        >
          <Text>동의하고 계속하기</Text>
        </Button>
      </View>
      </Animated.View>
    </Screen>
  );
}

function CheckMark({ checked }: { checked: boolean }) {
  return (
    <Icon
      as={checked ? CircleCheckBig : Circle}
      size={20}
      className={checked ? "text-primary" : "text-card-foreground"}
    />
  );
}

export { TermsScreen };
