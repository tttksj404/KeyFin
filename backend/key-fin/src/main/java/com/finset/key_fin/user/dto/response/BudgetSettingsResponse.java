package com.finset.key_fin.user.dto.response;

import com.finset.key_fin.user.entity.UserSettings;
import io.swagger.v3.oas.annotations.media.Schema;

public record BudgetSettingsResponse(
		@Schema(description = "예산 기준일(주기 시작일, 1~28)", example = "25")
		int budgetAnchorDay
) {
	public static BudgetSettingsResponse from(UserSettings settings) {
		return new BudgetSettingsResponse(settings.getBudgetAnchorDay());
	}
}
