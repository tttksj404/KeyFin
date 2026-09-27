package com.finset.key_fin.notification.service;

import java.time.LocalTime;
import com.finset.key_fin.notification.entity.NotificationType;
import com.finset.key_fin.user.entity.UserSettings;
import org.springframework.stereotype.Component;

@Component
public class NotificationPushPolicy {
	public enum Decision {
		ALLOW, SETTINGS_MISSING, INVALID_QUIET_HOURS, TYPE_DISABLED, QUIET_HOURS, NO_ACTIVE_DEVICE
	}

	public Decision evaluate(UserSettings settings, NotificationType type, LocalTime now) {
		if (settings == null) return Decision.SETTINGS_MISSING;
		LocalTime start = settings.getQuietHoursStart();
		LocalTime end = settings.getQuietHoursEnd();
		if ((start == null) != (end == null) || (start != null && start.equals(end))) {
			return Decision.INVALID_QUIET_HOURS;
		}
		boolean enabled = switch (type) {
			case COACHING -> settings.isNotiCoaching();
			case BUDGET_ALERT -> settings.isNotiBudgetAlert();
			case TRANSFER_REQUEST -> settings.isNotiTransfer();
			case CLEANUP -> settings.isNotiCleanup();
			case WARNING, SUBSCRIPTION_CARD -> true;
		};
		if (!enabled) return Decision.TYPE_DISABLED;
		if (start != null) {
			boolean quiet = start.isBefore(end)
					? !now.isBefore(start) && now.isBefore(end)
					: !now.isBefore(start) || now.isBefore(end);
			if (quiet) return Decision.QUIET_HOURS;
		}
		return Decision.ALLOW;
	}
}
