import { View } from "react-native";

import { LinkManagementScreen } from "@/features/link/components/LinkManagementScreen";

// PAGE-32 연결 관리 (P1, FR-USR-05). 마이 탭에서 들어온다.
export default function LinksRoute() {
  return (
    <View className="flex-1 bg-background">
      <LinkManagementScreen />
    </View>
  );
}
