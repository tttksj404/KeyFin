import type { LucideIcon } from "lucide-react-native";
import { View } from "react-native";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Text } from "@/components/ui/text";
import { cn } from "@/lib/utils";

type EmptyStateProps = {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: { label: string; onPress: () => void; disabled?: boolean };
  className?: string;
};

function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <View className={cn("items-center gap-3 px-6 py-10", className)} accessibilityLiveRegion="polite">
      <Icon as={icon} size={40} className="text-card-foreground/70" />
      <Text className="text-center text-h3">{title}</Text>
      {description ? (
        <Text className="text-center text-body-sm text-card-foreground">{description}</Text>
      ) : null}
      {action ? (
        <Button
          variant="secondary"
          className="mt-2 h-button-md rounded-lg px-6"
          onPress={action.onPress}
          disabled={action.disabled}
          accessibilityState={{ disabled: action.disabled === true }}
        >
          <Text className="text-button">{action.label}</Text>
        </Button>
      ) : null}
    </View>
  );
}

export { EmptyState };
export type { EmptyStateProps };
