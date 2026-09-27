import {
  ArrowLeftRight,
  Banknote,
  ChartColumn,
  CreditCard,
  PiggyBank,
  Receipt,
  Smartphone,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react-native";
import { Pressable, View } from "react-native";

import { Icon } from "@/components/ui/icon";
import { Text } from "@/components/ui/text";

type QuickMenuItem = {
  key: string;
  label: string;
  icon: LucideIcon;
  iconClassName: string;
};

const QUICK_MENU_ITEMS: readonly QuickMenuItem[] = [
  { key: "accounts", label: "계좌·카드", icon: Wallet, iconClassName: "text-primary" },
  { key: "transfer", label: "이체", icon: ArrowLeftRight, iconClassName: "text-destructive" },
  { key: "withdraw", label: "출금", icon: Banknote, iconClassName: "text-info" },
  { key: "mobile", label: "휴대폰 충전", icon: Smartphone, iconClassName: "text-warning" },
  { key: "bills", label: "공과금", icon: Receipt, iconClassName: "text-positive" },
  { key: "savings", label: "저축", icon: PiggyBank, iconClassName: "text-primary" },
  { key: "credit-card", label: "신용카드", icon: CreditCard, iconClassName: "text-highlight" },
  { key: "report", label: "거래 내역", icon: ChartColumn, iconClassName: "text-primary" },
  { key: "beneficiary", label: "받는 사람", icon: Users, iconClassName: "text-destructive" },
];

type QuickMenuProps = {
  onSelect?: (key: string) => void;
};

function QuickMenu({ onSelect }: QuickMenuProps) {
  return (
    <View className="-m-2 flex-row flex-wrap">
      {QUICK_MENU_ITEMS.map((item) => (
        <View key={item.key} className="w-1/3 p-2">
          <Pressable
            onPress={onSelect ? () => onSelect(item.key) : undefined}
            accessibilityRole="button"
            accessibilityLabel={item.label}
            className="aspect-square items-center justify-center gap-2 rounded-lg border border-transparent bg-card p-3 shadow-sm shadow-black/5 active:bg-muted dark:border-border dark:shadow-none"
          >
            <Icon as={item.icon} size={28} className={item.iconClassName} />
            <Text className="text-center text-label text-card-foreground" numberOfLines={2}>
              {item.label}
            </Text>
          </Pressable>
        </View>
      ))}
    </View>
  );
}

export { QUICK_MENU_ITEMS, QuickMenu };
export type { QuickMenuItem, QuickMenuProps };
