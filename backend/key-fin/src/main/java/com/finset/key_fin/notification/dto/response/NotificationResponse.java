package com.finset.key_fin.notification.dto.response;

import java.time.LocalDateTime;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.finset.key_fin.notification.entity.InboxNotification;
import com.finset.key_fin.notification.entity.NotificationType;
import io.swagger.v3.oas.annotations.media.Schema;

public record NotificationResponse(
		long id,
		NotificationType type,
		@Schema(maxLength = 100) String title,
		@Schema(nullable = true) String body,
		@Schema(maxLength = 30, nullable = true) String refId,
		boolean requiresAction,
		@JsonProperty("isRead") boolean isRead,
		@Schema(description = "생성 시각 (Asia/Seoul)", example = "2026-09-16T22:00:00") LocalDateTime createdAt
) {
	public static NotificationResponse from(InboxNotification notification) {
		return new NotificationResponse(notification.id(), notification.type(), notification.title(),
				notification.body(), notification.refId(), notification.requiresAction(),
				notification.isRead(), notification.createdAt());
	}
}
