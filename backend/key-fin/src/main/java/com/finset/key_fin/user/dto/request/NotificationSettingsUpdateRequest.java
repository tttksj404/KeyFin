package com.finset.key_fin.user.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotNull;

import java.time.LocalTime;

public record NotificationSettingsUpdateRequest(
		@Schema(description = "코칭 알림 수신 여부", example = "true", requiredMode = Schema.RequiredMode.REQUIRED)
		@NotNull(message = "코칭 알림 수신 여부는 필수입니다.")
		Boolean notiCoaching,

		@Schema(description = "예산 잔액 알림 수신 여부", example = "true", requiredMode = Schema.RequiredMode.REQUIRED)
		@NotNull(message = "예산 잔액 알림 수신 여부는 필수입니다.")
		Boolean notiBudgetAlert,

		@Schema(description = "이체 알림 수신 여부", example = "true", requiredMode = Schema.RequiredMode.REQUIRED)
		@NotNull(message = "이체 알림 수신 여부는 필수입니다.")
		Boolean notiTransfer,

		@Schema(description = "정리 알림 수신 여부", example = "false", requiredMode = Schema.RequiredMode.REQUIRED)
		@NotNull(message = "정리 알림 수신 여부는 필수입니다.")
		Boolean notiCleanup,

		@Schema(description = "방해금지 시작 시각. 종료 시각과 함께 null이면 방해금지 해제", example = "23:00", nullable = true)
		LocalTime quietHoursStart,

		@Schema(description = "방해금지 종료 시각. 시작 시각과 함께 null이면 방해금지 해제", example = "08:00", nullable = true)
		LocalTime quietHoursEnd
) {
}
