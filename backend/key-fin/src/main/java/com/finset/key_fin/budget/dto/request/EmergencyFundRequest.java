package com.finset.key_fin.budget.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;

@Schema(description = "비상금(가상 풀) 월 금액 설정 요청")
public record EmergencyFundRequest(
		@Schema(description = "비상금 금액(원, 0 이상 1,000원 단위). 0이면 해제", example = "200000")
		@NotNull
		@Min(0)
		Long amount
) {
}
