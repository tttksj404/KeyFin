package com.finset.key_fin.budget.dto.request;

import java.util.List;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;

@Schema(description = "예산 승인·조정 요청 — 봉투 7종 전부의 확정 금액")
public record BudgetConfirmRequest(
		@NotEmpty
		@Valid
		List<EnvelopeAmount> envelopes
) {

	@Schema(description = "봉투별 확정 금액")
	public record EnvelopeAmount(
			@Schema(description = "봉투 ID", example = "1")
			@NotNull
			Integer envelopeId,

			@Schema(description = "확정 금액(원, 1,000원 단위)", example = "280000")
			@NotNull
			@Min(0)
			Long amount
	) {
	}
}
