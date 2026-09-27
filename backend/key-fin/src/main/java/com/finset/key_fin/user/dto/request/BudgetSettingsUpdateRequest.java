package com.finset.key_fin.user.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;

public record BudgetSettingsUpdateRequest(
		@Schema(description = "예산 기준일(주기 시작일, 1~28)", example = "25", requiredMode = Schema.RequiredMode.REQUIRED)
		@NotNull(message = "예산 기준일은 필수입니다.")
		@Min(value = 1, message = "예산 기준일은 1 이상이어야 합니다.")
		@Max(value = 28, message = "예산 기준일은 28 이하여야 합니다.")
		Integer budgetAnchorDay
) {
}
