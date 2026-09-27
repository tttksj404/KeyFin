import { LogOut } from "lucide-react-native";
import { View } from "react-native";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Text } from "@/components/ui/text";
import { useLogout } from "@/features/auth/api/queries";

/**
 * 로그아웃하면 서버의 Refresh Token 이 지워지고 기기의 토큰·캐시도 비워진다.
 * 화면 이동은 (tabs) 레이아웃이 비로그인 상태를 보고 알아서 로그인으로 보낸다.
 */
function LogoutButton() {
  const logout = useLogout();

  return (
    <Button
      variant="outline"
      size="lg"
      className="h-button-lg flex-row items-center gap-2 rounded-lg"
      onPress={() => logout.mutate()}
      disabled={logout.isPending}
      accessibilityLabel="로그아웃"
    >
      <View className="flex-row items-center gap-2">
        <Icon as={LogOut} size={18} className="text-foreground" />
        <Text>{logout.isPending ? "로그아웃 중…" : "로그아웃"}</Text>
      </View>
    </Button>
  );
}

export { LogoutButton };
