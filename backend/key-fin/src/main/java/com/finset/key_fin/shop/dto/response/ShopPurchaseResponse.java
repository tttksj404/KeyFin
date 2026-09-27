package com.finset.key_fin.shop.dto.response;

import com.finset.key_fin.item.entity.ItemCategory;
import io.swagger.v3.oas.annotations.media.Schema;

import static io.swagger.v3.oas.annotations.media.Schema.RequiredMode.REQUIRED;

@Schema(description = "구매한 상품의 보유 내역과 구매 직후 코인 잔액")
public record ShopPurchaseResponse(
		@Schema(requiredMode = REQUIRED) Long itemId,
		@Schema(requiredMode = REQUIRED) ItemCategory itemCategory,
		@Schema(description = "아바타 보유 내역 ID. 가구 구매이면 null", types = {"integer", "null"}, format = "int64", requiredMode = REQUIRED) Long userItemId,
		@Schema(description = "가구 보유 내역 ID. 아바타 구매이면 null", types = {"integer", "null"}, format = "int64", requiredMode = REQUIRED) Long userFurnitureId,
		@Schema(description = "실제 구매 가격", minimum = "0", requiredMode = REQUIRED) int price,
		@Schema(description = "구매 직후 코인 잔액", minimum = "0", requiredMode = REQUIRED) int balance
) {
}
