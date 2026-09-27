import { isApiError } from "@/api/error";
import { FURNITURE, isWallItemId } from "@/features/room/catalog";
import { getSpriteRect, type FurnitureType, type SceneRect } from "@/features/room/model";
import { facingOf, placementView, type Placement } from "@/features/room/scene";

export type StickerFurniture = {
  userFurnitureId: number;
  furnitureType: FurnitureType | null;
  stickerAttached: boolean;
  placementStatus: string | null;
};

/** 편집 사본에서도 서버와 같은 기본 가구 스타일 이전을 미리 보여 준다. 일반 가구는 보유 ID에 딱지가 남는다. */
export function stickerPlacements(placements: readonly Placement[], owned: readonly StickerFurniture[], editing = false): Placement[] {
  const byId = new Map(owned.map((item) => [item.userFurnitureId, item]));
  const types = new Set(owned.filter((item) => item.placementStatus === "FLOOR" && item.stickerAttached && item.furnitureType !== null)
    .map((item) => item.furnitureType));
  return placements.filter((placement) => {
    if (isWallItemId(placement.itemId) || FURNITURE[placement.itemId].slot !== "FLOOR" || (placement.surface ?? "FLOOR") !== "FLOOR") return false;
    const item = placement.userFurnitureId === undefined ? undefined : byId.get(placement.userFurnitureId);
    return item && (editing && item.furnitureType !== null ? types.has(item.furnitureType) : item.stickerAttached);
  });
}

/** 이미지 내부의 중심 비율, 씬 단위 폭, 기울기(도). 색상에 관계없이 같은 표면에 붙인다. */
type LabelLayout = { x: number; y: number; width: number; angle: number };
const label = (x: number, y: number, width: number, angle = 0): LabelLayout => ({ x, y, width, angle });
const pair = (right: LabelLayout, left: LabelLayout = { ...right, x: 1 - right.x, angle: -right.angle }) => ({ FRONT_RIGHT: right, FRONT_LEFT: left });
export const STICKER_LAYOUTS = {
  bed: pair(label(0.51, 0.45, 28, 26)),
  sofa: pair(label(0.43, 0.42, 27, 26)),
  coffee_table: pair(label(0.50, 0.34, 23, 26)),
  desk: pair(label(0.48, 0.30, 24, 26)),
  dining_table: pair(label(0.50, 0.28, 25, 26)),
  dining_chair: pair(label(0.33, 0.23, 14, -26)),
  bookcase: pair(label(0.62, 0.38, 18, -26)),
  wardrobe: pair(label(0.62, 0.42, 24, -26)),
  nightstand: pair(label(0.68, 0.48, 14, -26)),
  refrigerator: pair(label(0.70, 0.36, 19, -26)),
  tv_set: pair(label(0.48, 0.36, 23, -26)),
  decor_arc_floor_lamp: pair(label(0.82, 0.14, 13, 0), label(0.78, 0.28, 13, 0)),
  decor_checker_rug: pair(label(0.55, 0.56, 24, 26)),
  decor_oval_rug: pair(label(0.55, 0.56, 23, 26)),
  plant_monstera_terracotta: pair(label(0.53, 0.76, 14, 0), label(0.54, 0.76, 14, 0)),
  plant_palm_blue_wave: pair(label(0.53, 0.78, 14, 0), label(0.48, 0.78, 14, 0)),
  plant_rubber_brass: pair(label(0.50, 0.70, 13, 0), label(0.50, 0.70, 13, 0)),
  plant_sansevieria_ivory: pair(label(0.52, 0.79, 12, 0), label(0.49, 0.79, 12, 0)),
} as const;

const DEFAULT_KINDS: Record<string, string> = { sofa_default: "sofa", tv_default: "tv_set", fridge_default: "refrigerator" };

export function stickerLayout(placement: Placement): LabelLayout | null {
  if (isWallItemId(placement.itemId) || FURNITURE[placement.itemId].slot !== "FLOOR") return null;
  const kind = DEFAULT_KINDS[placement.itemId] ?? placement.itemId.replace(/_(original|black|pink|sunset)$/, "");
  return STICKER_LAYOUTS[kind as keyof typeof STICKER_LAYOUTS]?.[facingOf(placement)] ?? null;
}

/** 렌더러와 터치 영역이 함께 쓰는 좌표. 문자는 반전하지 않고 회전만 한다. */
export function stickerGeometry(placement: Placement): { rect: SceneRect; angle: number } | null {
  const layout = stickerLayout(placement);
  if (!layout) return null;
  const view = placementView(placement);
  const furniture = getSpriteRect(placement.anchor, view.size, view.anchor);
  const height = layout.width * 256 / 480;
  return { rect: { x: furniture.x + furniture.width * layout.x - layout.width / 2,
    y: furniture.y + furniture.height * layout.y - height / 2, width: layout.width, height }, angle: layout.angle * Math.PI / 180 };
}

export function stickerErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    switch (error.code) {
      case "ROOM_001": return "바닥에 설치한 가구의 딱지만 제거할 수 있어요.";
      case "ROOM_003": return "이미 제거된 딱지예요. 방 상태를 다시 확인해 주세요.";
      case "NETWORK": case "TIMEOUT": return "연결 상태를 확인한 뒤 다시 시도해 주세요.";
    }
  }
  return "딱지를 제거하지 못했어요. 잠시 후 다시 시도해 주세요.";
}
