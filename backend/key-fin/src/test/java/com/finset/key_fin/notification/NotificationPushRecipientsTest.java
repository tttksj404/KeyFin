package com.finset.key_fin.notification;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;
import com.finset.key_fin.notification.entity.NotificationType;
import com.finset.key_fin.notification.repository.PushDeviceRepository;
import com.finset.key_fin.notification.service.NotificationPushPolicy;
import com.finset.key_fin.notification.service.NotificationPushRecipients;
import com.finset.key_fin.user.repository.UserSettingsRepository;
import org.junit.jupiter.api.Test;
import static com.finset.key_fin.notification.service.NotificationPushPolicy.Decision.*;
import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

class NotificationPushRecipientsTest {
	private final UserSettingsRepository settingsRepository = mock(UserSettingsRepository.class);
	private final PushDeviceRepository devices = mock(PushDeviceRepository.class);
	private final Clock clock = Clock.fixed(Instant.parse("2026-09-18T14:00:00Z"), ZoneOffset.UTC);
	private final NotificationPushRecipients recipients = new NotificationPushRecipients(
			settingsRepository, devices, new NotificationPushPolicy(), clock);

	@Test
	void interpretsUtcClockAsKstAndDoesNotReadDevicesWhenQuiet() {
		var settings = NotificationPushPolicyTest.settings();
		settings.updateNotificationSettings(true, true, true, true, LocalTime.of(23, 0), LocalTime.of(8, 0));
		when(settingsRepository.findById(1L)).thenReturn(Optional.of(settings));
		var result = recipients.select(1, NotificationType.COACHING);
		assertThat(result.decision()).isEqualTo(QUIET_HOURS);
		assertThat(result.devices()).isEmpty();
		verifyNoInteractions(devices);
	}

	@Test
	void missingSettingsDoNotDefaultToOptIn() {
		when(settingsRepository.findById(1L)).thenReturn(Optional.empty());
		assertThat(recipients.select(1, NotificationType.WARNING).decision()).isEqualTo(SETTINGS_MISSING);
		verifyNoInteractions(devices);
	}

	@Test
	void noActiveDevicesSkipsDelivery() {
		when(settingsRepository.findById(1L)).thenReturn(Optional.of(NotificationPushPolicyTest.settings()));
		when(devices.findActiveByUserId(1L)).thenReturn(List.of());
		assertThat(recipients.select(1, NotificationType.WARNING).decision()).isEqualTo(NO_ACTIVE_DEVICE);
	}
}
