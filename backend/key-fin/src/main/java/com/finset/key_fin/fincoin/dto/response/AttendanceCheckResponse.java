package com.finset.key_fin.fincoin.dto.response;

import io.swagger.v3.oas.annotations.media.Schema;

import static io.swagger.v3.oas.annotations.media.Schema.RequiredMode.REQUIRED;

@Schema(description = "출석 보상 처리 결과")
public record AttendanceCheckResponse(
		@Schema(description = "이번 요청의 지급량. 첫 출석은 10, 당일 재요청은 0", example = "10", requiredMode = REQUIRED)
		int granted,
		@Schema(description = "출석 요청 처리 시점의 코인 잔액", example = "1260", requiredMode = REQUIRED)
		int balance
) {
}
