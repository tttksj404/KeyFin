package com.finset.key_fin.user.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

public record TransferSettingsUpdateRequest(
		@Schema(description = "이체 동의 여부", example = "true", requiredMode = Schema.RequiredMode.REQUIRED)
		@NotNull(message = "이체 동의 여부는 필수입니다.")
		Boolean transferConsent,

		@Schema(description = "1회 이체 한도(원). null이면 한도 미설정", example = "1000000", nullable = true)
		@Positive(message = "1회 이체 한도는 0보다 커야 합니다.")
		Long transferLimitOnce,

		@Schema(description = "1일 이체 한도(원). null이면 한도 미설정", example = "2000000", nullable = true)
		@Positive(message = "1일 이체 한도는 0보다 커야 합니다.")
		Long transferLimitDaily
) {
}
