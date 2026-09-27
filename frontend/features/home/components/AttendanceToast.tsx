import { Coins } from "lucide-react-native";
import * as React from "react";
import { View } from "react-native";

import { Icon } from "@/components/ui/icon";
import { Text } from "@/components/ui/text";
import { formatKRW } from "@/lib/money";

// Pencil home/p0 (EWfx2) AttendanceToast (oEJOQ): 방 상단 중앙 알약 · bg-inverse · 아이콘 14 + 12/600. 3초 뒤 사라진다.
export const ATTENDANCE_TOAST_MS = 3000;

type AttendanceToastProps = {
  granted: number;
};

function AttendanceToast({ granted }: AttendanceToastProps) {
  const [visible, setVisible] = React.useState(true);

  React.useEffect(() => {
    const timer = setTimeout(() => setVisible(false), ATTENDANCE_TOAST_MS);
    return () => clearTimeout(timer);
  }, []);

  if (!visible) return null;

  const label = `출석 +${formatKRW(String(granted), { unit: false })} 코인`;

  return (
    <View className="pointer-events-none absolute left-0 right-0 top-24 items-center">
      <View className="flex-row items-center gap-1.5 rounded-full bg-inverse px-3 py-1.5" accessible accessibilityLiveRegion="polite" accessibilityLabel={label}>
        <Icon as={Coins} size={14} className="text-inverse-foreground" />
        <Text className="text-caption text-inverse-foreground">{label}</Text>
      </View>
    </View>
  );
}

export { AttendanceToast };
export type { AttendanceToastProps };
