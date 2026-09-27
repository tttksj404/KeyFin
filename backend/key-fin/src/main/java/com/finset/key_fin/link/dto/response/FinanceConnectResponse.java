package com.finset.key_fin.link.dto.response;

import io.swagger.v3.oas.annotations.media.Schema;

public record FinanceConnectResponse(
		@Schema(description = "금융망 연결 여부", example = "true")
		boolean connected
) {

	public static FinanceConnectResponse of(boolean connected) {
		return new FinanceConnectResponse(connected);
	}
}
