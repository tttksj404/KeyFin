import { Bus, Ellipsis, Gamepad2, HeartPulse, ShoppingBag, ShoppingCart, Utensils, type LucideIcon } from "lucide-react-native";

/**
 * 봉투 7종은 고정 id 다 (docs/api-contract.md §4). 이름은 서버 응답을 쓰고,
 * 순서·짧은 표시명·아이콘은 클라이언트 상수로 둔다 (docs/frontend-spec.md §5).
 * 아이콘은 Pencil budget (kvc1e) EnvelopeList (MhHC7) 의 Tile 안 lucide 이름이다.
 */
export const ENVELOPE_CATALOG = [
  { id: 1, name: "외식", shortName: "외식", icon: Utensils, tone: tone("dining") },
  { id: 2, name: "교통비", shortName: "교통", icon: Bus, tone: tone("transport") },
  { id: 3, name: "의료·건강", shortName: "의료", icon: HeartPulse, tone: tone("health") },
  { id: 4, name: "취미·여가", shortName: "여가", icon: Gamepad2, tone: tone("leisure") },
  { id: 5, name: "쇼핑", shortName: "쇼핑", icon: ShoppingBag, tone: tone("shopping") },
  { id: 6, name: "편의점·마트·잡화", shortName: "마트", icon: ShoppingCart, tone: tone("grocery") },
  { id: 7, name: "기타", shortName: "기타", icon: Ellipsis, tone: tone("etc") },
] as const;

type EnvelopeTone = { tile: string; icon: string; bar: string };

/**
 * 봉투 정체성 색(토큰 env-<이름> · env-<이름>-muted, 2026-09-14). NativeWind 는 클래스 이름을 조합해 만들면 못 찾으므로
 * 여기서 완성된 클래스로 둔다. 사용률 상태색(positive/warning/destructive)은 그대로 따로 쓴다.
 */
function tone(key: "dining" | "transport" | "health" | "leisure" | "shopping" | "grocery" | "etc"): EnvelopeTone {
  switch (key) {
    case "dining":
      return { tile: "bg-env-dining-muted", icon: "text-env-dining", bar: "bg-env-dining" };
    case "transport":
      return { tile: "bg-env-transport-muted", icon: "text-env-transport", bar: "bg-env-transport" };
    case "health":
      return { tile: "bg-env-health-muted", icon: "text-env-health", bar: "bg-env-health" };
    case "leisure":
      return { tile: "bg-env-leisure-muted", icon: "text-env-leisure", bar: "bg-env-leisure" };
    case "shopping":
      return { tile: "bg-env-shopping-muted", icon: "text-env-shopping", bar: "bg-env-shopping" };
    case "grocery":
      return { tile: "bg-env-grocery-muted", icon: "text-env-grocery", bar: "bg-env-grocery" };
    case "etc":
      return { tile: "bg-env-etc-muted", icon: "text-env-etc", bar: "bg-env-etc" };
  }
}

/** 봉투 색 클래스 묶음. 카탈로그에 없는 id 는 "기타" 색 */
export function envelopeTone(envelopeId: number): EnvelopeTone {
  return ENVELOPE_CATALOG.find((envelope) => envelope.id === envelopeId)?.tone ?? tone("etc");
}

/** 좁은 칸(차트 축)에 쓰는 이름. 카탈로그에 없는 id 면 서버 이름을 그대로 쓴다. */
export function envelopeShortName(envelopeId: number, fallback: string): string {
  return ENVELOPE_CATALOG.find((envelope) => envelope.id === envelopeId)?.shortName ?? fallback;
}

/** 봉투 아이콘. 카탈로그에 없는 id 는 "기타" 아이콘으로 떨어진다. */
export function envelopeIcon(envelopeId: number): LucideIcon {
  return ENVELOPE_CATALOG.find((envelope) => envelope.id === envelopeId)?.icon ?? Ellipsis;
}

/** 봉투 이름. 거래처럼 서버가 봉투 이름을 주지 않는 응답에서 쓴다. 카탈로그에 없는 id 는 "기타" */
export function envelopeName(envelopeId: number): string {
  return ENVELOPE_CATALOG.find((envelope) => envelope.id === envelopeId)?.name ?? "기타";
}
