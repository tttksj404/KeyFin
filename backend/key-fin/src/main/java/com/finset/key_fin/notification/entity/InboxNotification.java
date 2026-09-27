package com.finset.key_fin.notification.entity;

import java.time.LocalDateTime;

public record InboxNotification(
		long id,
		NotificationType type,
		String title,
		String body,
		String refId,
		boolean requiresAction,
		boolean isRead,
		LocalDateTime createdAt
) {
}
