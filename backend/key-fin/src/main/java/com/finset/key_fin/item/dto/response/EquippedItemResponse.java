package com.finset.key_fin.item.dto.response;

import com.finset.key_fin.item.entity.ItemSlotType;
import com.finset.key_fin.item.entity.UserItem;
import io.swagger.v3.oas.annotations.media.Schema;

import static io.swagger.v3.oas.annotations.media.Schema.RequiredMode.REQUIRED;

@Schema(description = "현재 장착한 아바타 아이템. 기본 에셋은 포함하지 않음")
public record EquippedItemResponse(
		@Schema(description = "보유 내역 ID", requiredMode = REQUIRED) Long userItemId,
		@Schema(description = "상품 ID", requiredMode = REQUIRED) Long itemId,
		@Schema(requiredMode = REQUIRED) ItemSlotType slotType,
		@Schema(requiredMode = REQUIRED) String assetKey
) {
	public static EquippedItemResponse from(UserItem userItem) {
		return new EquippedItemResponse(userItem.getId(), userItem.getItem().getId(),
				userItem.getEquippedSlot(), userItem.getItem().getAssetKey());
	}
}
