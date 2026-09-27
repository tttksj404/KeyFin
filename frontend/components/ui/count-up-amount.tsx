import type * as React from "react";

import { Text } from "@/components/ui/text";
import { useCountUp } from "@/hooks/use-count-up";
import { formatKRW, type KRW } from "@/lib/money";

type CountUpAmountProps = Omit<React.ComponentProps<typeof Text>, "children"> & {
  value: KRW;
  /** 보이는 값을 문자열로. 기본은 formatKRW */
  format?: (shown: KRW) => string;
  durationMs?: number;
};

// 큰 금액 하나가 화면에 들어올 때 0 에서 값까지 굴러 올라간다. 값이 바뀌면 지금 값에서 새 값으로 이어서 굴러간다.
// 소비 분석 합계·예산 잔액·예산 설정 총액처럼 화면의 주인공 숫자에만 쓴다(목록 행 금액에는 쓰지 않는다).
function CountUpAmount({ value, format = (shown) => formatKRW(shown), durationMs, ...textProps }: CountUpAmountProps) {
  const shown = useCountUp(value, durationMs);
  return (
    <Text maxFontSizeMultiplier={1.3} {...textProps}>
      {format(shown)}
    </Text>
  );
}

export { CountUpAmount };
