import { View } from "react-native";

import { CoachingChatScreen } from "@/features/coaching/components/CoachingChatScreen";

// PAGE-31 코칭 대화 (P1, FR-AI-04). 홈의 코치 고양이를 누르면 들어온다.
export default function CoachingChatRoute() {
  return (
    <View className="flex-1 bg-background">
      <CoachingChatScreen />
    </View>
  );
}
