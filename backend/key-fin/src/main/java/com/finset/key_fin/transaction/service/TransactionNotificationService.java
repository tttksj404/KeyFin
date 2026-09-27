package com.finset.key_fin.transaction.service;

import com.finset.key_fin.notification.entity.NotificationType;
import com.finset.key_fin.notification.service.NotificationService;
import com.finset.key_fin.transaction.event.PendingTransactionSaved;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.event.TransactionalEventListener;

import java.time.LocalDate;

@Slf4j
@Service
@RequiredArgsConstructor
public class TransactionNotificationService {

	private static final String PENDING_TITLE = "새로 정리할 거래가 있어요";
	private static final String CLEANUP_TITLE = "오늘의 소비를 정리해 볼까요?";

	private final NotificationService notificationService;
	private final TransactionNotificationCooldownService cooldown;

	@Transactional(propagation = Propagation.REQUIRES_NEW)
	@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
	public void notifyPendingTransaction(PendingTransactionSaved event) {
		try {
			notificationService.create(
					event.userId(),
					NotificationType.COACHING,
					PENDING_TITLE,
					pendingBody(event.merchantName(), event.amount()),
					Long.toString(event.transactionId()),
					true
			);
		} catch (RuntimeException exception) {
			log.warn("미분류 거래 즉시 알림 생성 실패: userId={}, transactionId={}",
					event.userId(), event.transactionId());
		}
	}

	public void notifyDailyCleanup(long userId, long pendingCount, LocalDate date) {
		if (!cooldown.acquireDailyCleanup(userId, date)) {
			return;
		}
		notificationService.create(
				userId,
				NotificationType.CLEANUP,
				CLEANUP_TITLE,
				"아직 분류하지 않은 거래가 " + pendingCount + "건 있어요.",
				null,
				true
		);
	}

	private String pendingBody(String merchantName, long amount) {
		if (merchantName == null || merchantName.isBlank()) {
			return "%,d원 거래를 분류해 주세요.".formatted(amount);
		}
		return "%s %,d원을 분류해 주세요.".formatted(merchantName, amount);
	}
}
