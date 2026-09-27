import { findOutfit, isOutfitKey, outfitByAssetKey, OUTFITS, OUTFIT_KEYS, OUTFIT_SPRITES } from "@/features/room/outfits";
import { shopItemSprite } from "@/features/shop/catalog";

describe("의상 세트 카탈로그", () => {
  it("세트 키는 서버 assetKey 와 같고 등급마다 세 장(서 있기·앉기·상점)을 갖춘다", () => {
    expect(OUTFIT_KEYS).toEqual(["outfit_epic_mage", "outfit_legendary_paladin", "outfit_mythic_dragon"]);
    for (const key of OUTFIT_KEYS) {
      const outfit = OUTFITS[key];
      expect(outfit.key).toBe(key);
      expect(outfit.name).not.toBe("");
      expect(outfit.standing).toBeDefined();
      expect(outfit.sitting).toBeDefined();
      expect(outfit.shop).toBeDefined();
    }
  });

  it("모르는 assetKey 는 세트가 아니라 null 이다 — 그 옷은 기본 차림으로 그린다", () => {
    expect(isOutfitKey("outfit_mythic_dragon")).toBe(true);
    expect(isOutfitKey("hair_default")).toBe(false);
    expect(outfitByAssetKey("outfit_mythic_dragon")).toBe(OUTFITS.outfit_mythic_dragon);
    expect(outfitByAssetKey("sofa_default")).toBeNull();
  });

  it("착장에서 세트를 찾을 때 카탈로그에 없는 기본 헤어·표정은 건너뛴다", () => {
    const equipped = [{ assetKey: "hair_default" }, { assetKey: "face_default" }, { assetKey: "outfit_legendary_paladin" }];
    expect(findOutfit(equipped)).toBe(OUTFITS.outfit_legendary_paladin);
    expect(findOutfit([{ assetKey: "hair_default" }])).toBeNull();
    expect(findOutfit([])).toBeNull();
  });

  it("미리 읽어 둘 스프라이트는 등급마다 서 있기·앉기 두 장씩이다", () => {
    expect(OUTFIT_SPRITES).toHaveLength(OUTFIT_KEYS.length * 2);
  });

  it("상점은 세트 assetKey 로 옷 그림을 찾고, 가구 키는 방 카탈로그에서 찾는다", () => {
    for (const key of OUTFIT_KEYS) {
      expect(shopItemSprite(key)).toBe(OUTFITS[key].shop);
    }
    expect(shopItemSprite("sofa_default")).not.toBeNull();
    // 서버가 다른 assetKey 를 주면 그림이 없다 — 상점은 아이콘으로 폴백한다
    expect(shopItemSprite("hat_blue")).toBeNull();
  });
});
