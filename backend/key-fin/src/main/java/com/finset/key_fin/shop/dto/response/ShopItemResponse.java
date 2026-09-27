package com.finset.key_fin.shop.dto.response;

import com.finset.key_fin.item.entity.Item;
import com.finset.key_fin.item.entity.ItemCategory;
import com.finset.key_fin.item.entity.ItemSlotType;
import io.swagger.v3.oas.annotations.media.Schema;

import static io.swagger.v3.oas.annotations.media.Schema.RequiredMode.REQUIRED;

@Schema(description = "판매 중인 상점 상품")
public record ShopItemResponse(
		@Schema(requiredMode = REQUIRED) Long itemId,
		@Schema(requiredMode = REQUIRED) ItemCategory itemCategory,
		@Schema(requiredMode = REQUIRED) ItemSlotType slotType,
		@Schema(requiredMode = REQUIRED) String name,
		@Schema(description = "코인 가격. 0이면 무료", requiredMode = REQUIRED) int price,
		@Schema(requiredMode = REQUIRED) String assetKey,
		@Schema(description = "상시 상품이면 null", types = {"string", "null"}, requiredMode = REQUIRED) String themeCode,
		@Schema(description = "현재 사용자 보유 여부", requiredMode = REQUIRED) boolean owned
) {
	public static ShopItemResponse from(Item item, boolean owned) {
		return new ShopItemResponse(item.getId(), item.getItemCategory(), item.getSlotType(),
				item.getName(), item.getPrice(), item.getAssetKey(), item.getThemeCode(), owned);
	}
}
