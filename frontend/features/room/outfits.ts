/**
 * 의상 세트 카탈로그 (FR-GAM-05).
 *
 * 아바타 옷은 부위별 파츠가 아니라 **세트 한 벌**이다 — 머리·상의·하의·신발이 한 장에 같이 그려진 캐릭터 이미지라
 * 부위를 나눠 겹쳐 그릴 수 없다(사용자 결정 2026-09-21). 그래서 화면은 부위 탭 없이 세트 목록만 보여 주고,
 * 세트를 입으면 방 씬의 캐릭터 그림이 통째로 바뀐다.
 *
 * 서버는 세트를 `item_category=AVATAR` · `slot_type=UPPER_BODY` 로 내려 준다(DB CHECK 가 SET 을 허용하지 않고
 * 백엔드는 고치지 않기로 했다 — 사용자 결정 2026-09-21). 부위 값은 계약 그대로 두고 화면에서만 '세트'로 부른다.
 * 한 벌만 입는 성질은 서버가 보장한다: 같은 부위의 기존 아이템을 자동으로 벗기므로 세트도 언제나 하나다.
 *
 * `key` = 서버 `items.asset_key` (백엔드 V19__seed_avatar_outfit_sets.sql, 2026-09-21 대조). 이 문자열이 스프라이트 조회 키라
 * 값이 다르면 그 세트는 그림이 안 나온다(그때는 기본 차림으로 폴백한다). 이름·가격도 V19 값이다 — 500·1,000·2,000 코인.
 * 스프라이트는 `scripts/assets/build-outfit-sprites.ps1` 로 만든다 —
 * 세트마다 서 있는 자세로 배율을 정하고 앉은 자세에도 같은 배율을 써서, 옷을 갈아입어도 키가 달라지지 않는다.
 */
export const OUTFIT_KEYS = ["outfit_epic_mage", "outfit_legendary_paladin", "outfit_mythic_dragon"] as const;
export type OutfitKey = (typeof OUTFIT_KEYS)[number];

export type Outfit = {
  key: OutfitKey;
  /** 상품 이름은 서버 값을 쓰고, 이 이름은 목·폴백용이다 */
  name: string;
  /** 방 씬 기본 자세. char1-idle 과 같은 캔버스(496×756)라 CHARACTER_SIZE 를 그대로 쓴다 */
  standing: number;
  /** 소파에 앉은 자세 */
  sitting: number;
  /** 상점·옷장 타일용 의상 그림(캐릭터 없이 옷만) */
  shop: number;
};

export const OUTFITS: Record<OutfitKey, Outfit> = {
  outfit_epic_mage: {
    key: "outfit_epic_mage",
    name: "에픽 마법사 의상 세트",
    standing: require("@/assets/sprites/outfits/outfit_epic_mage/standing.png"),
    sitting: require("@/assets/sprites/outfits/outfit_epic_mage/sitting.png"),
    shop: require("@/assets/sprites/outfits/outfit_epic_mage/shop.png"),
  },
  outfit_legendary_paladin: {
    key: "outfit_legendary_paladin",
    name: "레전더리 성기사 의상 세트",
    standing: require("@/assets/sprites/outfits/outfit_legendary_paladin/standing.png"),
    sitting: require("@/assets/sprites/outfits/outfit_legendary_paladin/sitting.png"),
    shop: require("@/assets/sprites/outfits/outfit_legendary_paladin/shop.png"),
  },
  outfit_mythic_dragon: {
    key: "outfit_mythic_dragon",
    name: "신화 용염 의상 세트",
    standing: require("@/assets/sprites/outfits/outfit_mythic_dragon/standing.png"),
    sitting: require("@/assets/sprites/outfits/outfit_mythic_dragon/sitting.png"),
    shop: require("@/assets/sprites/outfits/outfit_mythic_dragon/shop.png"),
  },
};

export function isOutfitKey(assetKey: string): assetKey is OutfitKey {
  return (OUTFIT_KEYS as readonly string[]).includes(assetKey);
}

/** 서버 assetKey 로 세트를 찾는다. 모르는 값이면 null 이라 부르는 쪽이 기본 차림으로 폴백한다 */
export function outfitByAssetKey(assetKey: string): Outfit | null {
  return isOutfitKey(assetKey) ? OUTFITS[assetKey] : null;
}

/**
 * 착장(`GET /room` 의 avatar.equipped)에서 입고 있는 세트를 찾는다.
 * 카탈로그에 없는 assetKey 뿐이면 null 이고, 부르는 쪽은 기본 캐릭터 그림을 그린다.
 */
export function findOutfit(equipped: readonly { assetKey: string }[]): Outfit | null {
  for (const item of equipped) {
    const outfit = outfitByAssetKey(item.assetKey);
    if (outfit) return outfit;
  }
  return null;
}

/** 방 씬에 미리 읽어 둘 세트 스프라이트. 갈아입는 순간 그림이 비지 않게 전부 데워 둔다 */
export const OUTFIT_SPRITES: readonly number[] = OUTFIT_KEYS.flatMap((key) => [OUTFITS[key].standing, OUTFITS[key].sitting]);
