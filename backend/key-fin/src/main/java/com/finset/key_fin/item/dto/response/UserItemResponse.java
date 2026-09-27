package com.finset.key_fin.item.dto.response;

import com.finset.key_fin.item.entity.ItemSlotType;
import com.finset.key_fin.item.entity.UserItem;
import io.swagger.v3.oas.annotations.media.Schema;

import static io.swagger.v3.oas.annotations.media.Schema.RequiredMode.REQUIRED;

@Schema(description = "사용자가 보유한 아바타 아이템")
public record UserItemResponse(
		@Schema(description = "보유 내역 ID. 장착·해제 요청에 사용", requiredMode = REQUIRED) Long userItemId,
		@Schema(description = "상품 ID", requiredMode = REQUIRED) Long itemId,
		@Schema(requiredMode = REQUIRED) String name,
		@Schema(requiredMode = REQUIRED) ItemSlotType slotType,
		@Schema(requiredMode = REQUIRED) String assetKey,
		@Schema(description = "현재 장착 여부", requiredMode = REQUIRED) boolean equipped
) {
	public static UserItemResponse from(UserItem userItem) {
		var item = userItem.getItem();
		return new UserItemResponse(userItem.getId(), item.getId(), item.getName(),
				item.getSlotType(), item.getAssetKey(), userItem.isEquipped());
	}
}
