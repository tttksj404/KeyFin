package com.finset.key_fin.link.dto.response;

import io.swagger.v3.oas.annotations.media.Schema;

public record LinkAssetsResponse(
		@Schema(description = "이번 요청으로 새로 연결된 계좌 수", example = "1")
		int accounts,
		@Schema(description = "이번 요청으로 새로 연결된 카드 수", example = "1")
		int cards
) {
}
