package com.finset.key_fin.shop.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

public record ShopPurchaseRequest(
		@Schema(description = "구매할 상품 ID", example = "123", minimum = "1", requiredMode = Schema.RequiredMode.REQUIRED)
		@NotNull @Positive Long itemId
) {
}
