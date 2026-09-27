import { useRouter } from "expo-router";
import { ChevronRight, User } from "lucide-react-native";
import { Pressable, View } from "react-native";

import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { useHeaderlessTop } from "@/components/ui/screen";
import { Text } from "@/components/ui/text";
import { LogoutButton } from "@/features/auth/components/LogoutButton";
import { WithdrawAccountButton } from "@/features/auth/components/WithdrawAccountButton";
import { selectUserName, useAuthStore } from "@/features/auth/store";

const MENU = [
  { label: "설정", route: "/my/settings" },
  { label: "연결 관리", route: "/my/links" },
] as const;

// Pencil 마이페이지 (n374g) — 시안은 있고 구현 전. 설정(PAGE-27)·연결 관리(PAGE-32) 진입과 로그아웃만 먼저 붙였다.
// 탭 화면이라 제목 헤더를 두지 않는다(2026-09-18).
export default function MyRoute() {
  const router = useRouter();
  const userName = useAuthStore(selectUserName);
  const topInset = useHeaderlessTop();

  return (
    <View className="flex-1 bg-background" style={{ paddingTop: topInset }}>
      <View className="flex-1 bg-background px-6">
      {userName === null ? null : <Text className="text-body text-card-foreground">{userName}님</Text>}
      <View className="gap-2 pt-6">
        {MENU.map((item) => (
          <Pressable
            key={item.route}
            accessibilityRole="button"
            accessibilityLabel={item.label}
            className="min-h-touch flex-row items-center justify-between rounded-lg border border-border bg-card px-4 py-3 active:opacity-70"
            onPress={() => router.push(item.route)}
          >
            <Text className="text-label text-foreground">{item.label}</Text>
            <Icon as={ChevronRight} size={18} className="text-card-foreground" />
          </Pressable>
        ))}
      </View>

      <EmptyState icon={User} title="준비 중인 화면이에요" description="프로필은 아직 준비 중이에요." />
      <View className="gap-1 pb-6">
        <LogoutButton />
        <WithdrawAccountButton />
      </View>
      </View>
    </View>
  );
}
