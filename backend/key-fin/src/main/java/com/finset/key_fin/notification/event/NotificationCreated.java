package com.finset.key_fin.notification.event;

import com.finset.key_fin.notification.entity.NotificationType;

public record NotificationCreated(long notificationId, long userId, NotificationType type,
		String title, String body, String refId, boolean requiresAction) {
	@Override
	public String toString() {
		return "NotificationCreated[notificationId=" + notificationId + "]";
	}
}
