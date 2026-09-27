import { Pressable, View } from "react-native";

import { Text } from "@/components/ui/text";
import { envelopeShortName, envelopeTone } from "@/features/budget/catalog";
import { envelopeHealth, usedBarPercent, usedPercent, type BudgetEnvelope, type EnvelopeHealth } from "@/features/budget/model";
import { formatKRW } from "@/lib/money";
import { cn } from "@/lib/utils";

// Pencil home/p0 EnvelopeChart (KZBd3): 봉투 7종 사용률 세로 막대. 위 퍼센트, 아래 짧은 이름.
// 여유(good)면 봉투 정체성 색, 남은 30% 미만이면 노랑, 초과면 빨강에 100% 로 자른다 — 상태색이 정체성 색보다 우선한다(2026-09-14).
// 오른쪽 위의 "남은 30% 미만 노랑 · 초과 빨강" 설명은 뺐고(사용자 요청 2026-09-23), 막대는 시트를 키우면서 80 → 128pt 로 늘렸다.
function fillClass(envelopeId: number, health: EnvelopeHealth): string {
  if (health === "good") return envelopeTone(envelopeId).bar;
  if (health === "warning") return "bg-warning";
  if (health === "over") return "bg-destructive";
  return "bg-muted";
}

type EnvelopeChartProps = {
  envelopes: BudgetEnvelope[];
  /** 막대를 탭하면 그 봉투의 상세(PAGE-23)로 보낸다 */
  onSelect?: (envelopeId: number) => void;
};

function EnvelopeChart({ envelopes, onSelect }: EnvelopeChartProps) {
  return (
    <View className="gap-2">
      <Text className="text-caption text-primary-foreground">봉투별 사용률</Text>
      <View className="flex-row items-end gap-1.5">
        {envelopes.map((envelope) => (
          <EnvelopeBar key={envelope.envelopeId} envelope={envelope} onSelect={onSelect} />
        ))}
      </View>
    </View>
  );
}

// 확정액 0 인 봉투는 잔여율이 없어 빈 막대다. 쓴 돈이 있으면(over) 사용률 대신 "초과" 라고 적는다(사용자 결정 2026-09-12).
function EnvelopeBar({ envelope, onSelect }: { envelope: BudgetEnvelope; onSelect?: (envelopeId: number) => void }) {
  const health = envelopeHealth(envelope);
  const used = envelope.remainingRate === null ? null : usedPercent(envelope.remainingRate);
  const barPercent = usedBarPercent(envelope.remainingRate);
  const usedText = used === null ? (health === "over" ? "초과" : "-") : `${used}%`;
  const remainingText = envelope.remaining === null ? "" : `, 남은 ${formatKRW(envelope.remaining)}`;

  return (
    <Pressable
      className="flex-1 items-center gap-1 active:opacity-70"
      accessible
      accessibilityRole={onSelect ? "button" : undefined}
      accessibilityLabel={`${envelope.name} 사용률 ${usedText}${remainingText}`}
      accessibilityHint={onSelect ? "봉투 상세를 엽니다" : undefined}
      disabled={onSelect === undefined}
      onPress={onSelect === undefined ? undefined : () => onSelect(envelope.envelopeId)}
    >
      <Text className="text-caption tabular-nums text-primary-foreground">{usedText}</Text>
      <View className="h-32 w-6 justify-end overflow-hidden rounded-md bg-accent">
        <View className={cn("w-full rounded-md", fillClass(envelope.envelopeId, health))} style={{ height: `${barPercent}%` }} />
      </View>
      <Text className="text-caption text-primary-foreground" numberOfLines={1}>
        {envelopeShortName(envelope.envelopeId, envelope.name)}
      </Text>
    </Pressable>
  );
}

export { EnvelopeChart };
export type { EnvelopeChartProps };
