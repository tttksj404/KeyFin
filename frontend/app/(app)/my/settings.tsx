import { View } from "react-native";

import { SettingsScreen } from "@/features/settings/components/SettingsScreen";

// PAGE-27 설정 상세. 마이 탭에서 들어온다. P0 범위인 이체 동의·한도만 다룬다.
export default function SettingsRoute() {
  return (
    <View className="flex-1 bg-background">
      <SettingsScreen />
    </View>
  );
}
