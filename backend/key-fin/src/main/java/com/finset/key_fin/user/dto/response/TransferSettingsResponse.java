package com.finset.key_fin.user.dto.response;

import com.finset.key_fin.user.entity.UserSettings;
import io.swagger.v3.oas.annotations.media.Schema;

public record TransferSettingsResponse(
		@Schema(description = "이체 동의 여부", example = "true")
		boolean transferConsent,

		@Schema(description = "1회 이체 한도(원)", example = "1000000", nullable = true)
		Long transferLimitOnce,

		@Schema(description = "1일 이체 한도(원)", example = "2000000", nullable = true)
		Long transferLimitDaily
) {
	public static TransferSettingsResponse from(UserSettings settings) {
		return new TransferSettingsResponse(
				settings.isTransferConsent(),
				settings.getTransferLimitOnce(),
				settings.getTransferLimitDaily()
		);
	}
}
