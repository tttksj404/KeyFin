package com.finset.key_fin.user.dto.response;

import com.finset.key_fin.user.entity.UserSettings;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.LocalTime;

public record NotificationSettingsResponse(
		@Schema(description = "코칭 알림 수신 여부", example = "true")
		boolean notiCoaching,

		@Schema(description = "예산 잔액 알림 수신 여부", example = "true")
		boolean notiBudgetAlert,

		@Schema(description = "이체 알림 수신 여부", example = "true")
		boolean notiTransfer,

		@Schema(description = "정리 알림 수신 여부", example = "false")
		boolean notiCleanup,

		@Schema(description = "방해금지 시작 시각. 방해금지를 사용하지 않으면 null", example = "23:00", nullable = true)
		LocalTime quietHoursStart,

		@Schema(description = "방해금지 종료 시각. 방해금지를 사용하지 않으면 null", example = "08:00", nullable = true)
		LocalTime quietHoursEnd
) {
	public static NotificationSettingsResponse from(UserSettings settings) {
		return new NotificationSettingsResponse(
				settings.isNotiCoaching(),
				settings.isNotiBudgetAlert(),
				settings.isNotiTransfer(),
				settings.isNotiCleanup(),
				settings.getQuietHoursStart(),
				settings.getQuietHoursEnd()
		);
	}
}
