package com.finset.key_fin.notification.service;

import java.time.Clock;
import java.time.LocalTime;
import java.time.ZoneId;
import java.util.List;
import com.finset.key_fin.notification.entity.NotificationType;
import com.finset.key_fin.notification.entity.PushDevice;
import com.finset.key_fin.notification.repository.PushDeviceRepository;
import com.finset.key_fin.notification.service.NotificationPushPolicy.Decision;
import com.finset.key_fin.user.repository.UserSettingsRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class NotificationPushRecipients {
	private static final ZoneId KST = ZoneId.of("Asia/Seoul");
	private final UserSettingsRepository settingsRepository;
	private final PushDeviceRepository deviceRepository;
	private final NotificationPushPolicy policy;
	private final Clock clock;

	@Transactional(propagation = Propagation.REQUIRES_NEW, readOnly = true)
	public Selection select(long userId, NotificationType type) {
		Decision decision = policy.evaluate(settingsRepository.findById(userId).orElse(null),
				type, LocalTime.ofInstant(clock.instant(), KST));
		if (decision != Decision.ALLOW) return new Selection(decision, List.of());
		// 저장소에서 탈퇴 사용자와 비활성 기기도 제외한다.
		List<PushDevice> devices = deviceRepository.findActiveByUserId(userId);
		return new Selection(devices.isEmpty() ? Decision.NO_ACTIVE_DEVICE : Decision.ALLOW, devices);
	}

	public record Selection(Decision decision, List<PushDevice> devices) {
		public Selection {
			devices = List.copyOf(devices);
		}
	}
}
