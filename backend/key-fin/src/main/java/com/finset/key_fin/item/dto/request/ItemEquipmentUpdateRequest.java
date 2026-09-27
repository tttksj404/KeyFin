package com.finset.key_fin.item.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotNull;

@Schema(description = "보유 아이템의 장착 상태 변경 요청")
public record ItemEquipmentUpdateRequest(
		@Schema(description = "true: 장착·교체, false: 해제", example = "true",
				requiredMode = Schema.RequiredMode.REQUIRED)
		@NotNull(message = "장착 여부는 필수입니다.")
		Boolean equipped
) {
}
