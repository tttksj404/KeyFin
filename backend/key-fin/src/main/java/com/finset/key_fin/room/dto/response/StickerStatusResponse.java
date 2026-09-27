package com.finset.key_fin.room.dto.response;

import io.swagger.v3.oas.annotations.media.Schema;

public record StickerStatusResponse(
		@Schema(description = "현재 설치된 바닥 가구에 남은 딱지 수 (보관 중인 딱지 제외)", minimum = "0", requiredMode = Schema.RequiredMode.REQUIRED) int count,
		@Schema(description = "현재 설치된 바닥 가구 수", minimum = "0", example = "7", requiredMode = Schema.RequiredMode.REQUIRED) int total,
		@Schema(description = "현재 설치된 바닥 가구에 제거할 딱지가 남아 있는지. 일일 횟수 제한은 없으며 호환성을 위해 필드명을 유지합니다.", requiredMode = Schema.RequiredMode.REQUIRED) boolean removableToday
) {
}
