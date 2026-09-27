import { Eye, EyeOff } from "lucide-react-native";
import { Pressable, View } from "react-native";

import { AmountText } from "@/components/ui/amount-text";
import { Icon } from "@/components/ui/icon";
import { Text } from "@/components/ui/text";
import type { AccountSummary } from "@/features/account/model";

type AccountCardProps = {
  account: AccountSummary;
  balanceHidden: boolean;
  onToggleBalanceHidden: () => void;
};

function AccountCard({ account, balanceHidden, onToggleBalanceHidden }: AccountCardProps) {
  const toggleLabel = balanceHidden ? "잔액 보기" : "잔액 숨기기";

  return (
    <View
      className="gap-6 rounded-lg bg-primary p-5"
      accessible
      accessibilityLabel={`${account.alias}, ${account.bankName}, ${account.maskedAccountNumber}`}
    >
      <View className="flex-row items-start justify-between">
        <View className="gap-1">
          <Text className="text-h2 text-primary-foreground">{account.alias}</Text>
          <Text className="text-body-sm text-primary-foreground/80">{account.bankName}</Text>
        </View>
        <Pressable
          onPress={onToggleBalanceHidden}
          accessibilityRole="button"
          accessibilityLabel={toggleLabel}
          hitSlop={8}
          className="h-touch w-touch items-center justify-center rounded-full active:bg-white/20"
        >
          <Icon as={balanceHidden ? EyeOff : Eye} className="text-primary-foreground" size={22} />
        </Pressable>
      </View>

      <View className="gap-1">
        <Text className="text-body tabular-nums text-primary-foreground/90">{account.maskedAccountNumber}</Text>
        <AmountText value={account.balance} size="md" hidden={balanceHidden} className="text-primary-foreground" />
      </View>
    </View>
  );
}

export { AccountCard };
export type { AccountCardProps };
