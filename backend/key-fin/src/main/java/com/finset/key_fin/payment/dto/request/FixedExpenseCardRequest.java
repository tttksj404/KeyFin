package com.finset.key_fin.payment.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotNull;

@Schema(description = "카드 정기결제의 결제 카드 지정 요청")
public record FixedExpenseCardRequest(
		@Schema(description = "결제 카드 ID — 본인의 관리 대상 카드", example = "8")
		@NotNull
		Long cardId
) {
}
