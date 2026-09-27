package com.finset.key_fin.notification;

import java.time.LocalTime;
import com.finset.key_fin.notification.entity.NotificationType;
import com.finset.key_fin.notification.service.NotificationPushPolicy;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.entity.UserSettings;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.EnumSource;
import org.springframework.test.util.ReflectionTestUtils;
import static com.finset.key_fin.notification.service.NotificationPushPolicy.Decision.*;
import static org.assertj.core.api.Assertions.assertThat;

class NotificationPushPolicyTest {
	private final NotificationPushPolicy policy = new NotificationPushPolicy();

	@ParameterizedTest
	@EnumSource(value = NotificationType.class, names = {"WARNING", "SUBSCRIPTION_CARD"}, mode = EnumSource.Mode.EXCLUDE)
	void onlyTheMatchingSwitchControlsEachType(NotificationType type) {
		UserSettings settings = settings();
		settings.updateNotificationSettings(type == NotificationType.COACHING, type == NotificationType.BUDGET_ALERT,
				type == NotificationType.TRANSFER_REQUEST, type == NotificationType.CLEANUP, null, null);
		assertThat(policy.evaluate(settings, type, LocalTime.NOON)).isEqualTo(ALLOW);
		settings.updateNotificationSettings(type != NotificationType.COACHING, type != NotificationType.BUDGET_ALERT,
				type != NotificationType.TRANSFER_REQUEST, type != NotificationType.CLEANUP, null, null);
		assertThat(policy.evaluate(settings, type, LocalTime.NOON)).isEqualTo(TYPE_DISABLED);
	}

	@ParameterizedTest
	@EnumSource(value = NotificationType.class, names = {"WARNING", "SUBSCRIPTION_CARD"})
	void warningIgnoresTypeSwitchesButRespectsQuietHours(NotificationType type) {
		UserSettings settings = settings();
		settings.updateNotificationSettings(false, false, false, false, LocalTime.of(23, 0), LocalTime.of(8, 0));
		assertThat(policy.evaluate(settings, type, LocalTime.NOON)).isEqualTo(ALLOW);
		assertThat(policy.evaluate(settings, type, LocalTime.MIDNIGHT)).isEqualTo(QUIET_HOURS);
	}

	@ParameterizedTest
	@CsvSource({
			"09:00,18:00,08:59:59,ALLOW", "09:00,18:00,09:00,QUIET_HOURS",
			"09:00,18:00,12:00,QUIET_HOURS", "09:00,18:00,17:59:59,QUIET_HOURS", "09:00,18:00,18:00,ALLOW",
			"23:00,08:00,22:59:59,ALLOW", "23:00,08:00,23:00,QUIET_HOURS",
			"23:00,08:00,00:00,QUIET_HOURS", "23:00,08:00,07:59:59,QUIET_HOURS", "23:00,08:00,08:00,ALLOW"
	})
	void quietHoursIncludeStartAndExcludeEnd(String start, String end, String now,
			NotificationPushPolicy.Decision expected) {
		UserSettings settings = settings();
		settings.updateNotificationSettings(true, true, true, true, LocalTime.parse(start), LocalTime.parse(end));
		assertThat(policy.evaluate(settings, NotificationType.COACHING, LocalTime.parse(now))).isEqualTo(expected);
	}

	@Test
	void missingOrCorruptSettingsFailClosedIncludingForWarning() {
		assertThat(policy.evaluate(null, NotificationType.WARNING, LocalTime.NOON)).isEqualTo(SETTINGS_MISSING);
		UserSettings settings = settings();
		for (LocalTime[] times : new LocalTime[][]{
				{LocalTime.NOON, null}, {null, LocalTime.NOON}, {LocalTime.NOON, LocalTime.NOON}}) {
			ReflectionTestUtils.setField(settings, "quietHoursStart", times[0]);
			ReflectionTestUtils.setField(settings, "quietHoursEnd", times[1]);
			assertThat(policy.evaluate(settings, NotificationType.WARNING, LocalTime.NOON)).isEqualTo(INVALID_QUIET_HOURS);
		}
	}

	static UserSettings settings() {
		return UserSettings.create(User.create("push@test.invalid", "encoded", "test"));
	}
}
