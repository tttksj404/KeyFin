package com.finset.key_fin.room.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

public record StickerRemovalRequest(
		@Schema(description = "딱지를 제거할 사용자 보유 가구 ID", requiredMode = Schema.RequiredMode.REQUIRED)
		@NotNull @Positive Long userFurnitureId
) {
}
