import { View } from "react-native";

import { NotificationInboxScreen } from "@/features/notification/components/NotificationInboxScreen";

// PAGE-28 알림함 (P1, FR-NTF-02). 홈 헤더 알림 버튼에서 들어온다.
export default function NotificationInboxRoute() {
  return (
    <View className="flex-1 bg-background">
      <NotificationInboxScreen />
    </View>
  );
}
