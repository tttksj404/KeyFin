import * as React from "react";

import { Text } from "@/components/ui/text";
import { formatKRW, signOfKRW, type KRW, type SignMode } from "@/lib/money";
import { cn } from "@/lib/utils";

type AmountSize = "lg" | "md" | "sm";

const SIZE_CLASS: Record<AmountSize, string> = {
  lg: "text-amount-lg",
  md: "text-amount-md",
  sm: "text-amount-sm",
};

const HIDDEN_TEXT = "••••••원";
const HIDDEN_LABEL = "잔액 숨김";

type AmountTextProps = Omit<React.ComponentProps<typeof Text>, "children"> & {
  value: KRW;
  size?: AmountSize;
  sign?: SignMode;
  hidden?: boolean;
};

function amountColorClass(value: KRW, sign: SignMode): string {
  const direction = signOfKRW(value);
  if (direction < 0) return "text-destructive";
  if (direction > 0 && sign === "always") return "text-positive";
  return "text-foreground";
}

function AmountText({ value, size = "md", sign = "auto", hidden = false, className, ...props }: AmountTextProps) {
  const text = hidden ? HIDDEN_TEXT : formatKRW(value, { sign });
  const colorClass = hidden ? "text-foreground" : amountColorClass(value, sign);

  return (
    <Text
      className={cn(SIZE_CLASS[size], "tabular-nums", colorClass, className)}
      accessibilityLabel={hidden ? HIDDEN_LABEL : text}
      maxFontSizeMultiplier={1.3}
      {...props}
    >
      {text}
    </Text>
  );
}

export { AmountText };
export type { AmountTextProps };
