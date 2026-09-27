package com.finset.key_fin.item.dto.response;

import io.swagger.v3.oas.annotations.media.Schema;
import java.util.List;

import static io.swagger.v3.oas.annotations.media.Schema.RequiredMode.REQUIRED;

public record AvatarEquipmentResponse(
		@Schema(description = "변경 후 전체 착장. HEAD, FACE, UPPER_BODY, LOWER_BODY, SOCKS, FOOTWEAR 순서. "
				+ "미장착 부위는 제외하며 모바일에서 기본 에셋을 표시. 모두 해제하면 빈 배열",
				requiredMode = REQUIRED)
		List<EquippedItemResponse> equipped
) {
}
