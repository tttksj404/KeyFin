package com.finset.key_fin.transaction.scheduler;

import com.finset.key_fin.transaction.repository.PendingTransactionSummary;
import com.finset.key_fin.transaction.repository.TransactionRepository;
import com.finset.key_fin.transaction.service.TransactionNotificationService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.Clock;
import java.time.LocalDate;
import java.util.concurrent.atomic.AtomicBoolean;

@Slf4j
@Component
@RequiredArgsConstructor
public class PendingTransactionNotificationScheduler {

	private final TransactionRepository transactionRepository;
	private final TransactionNotificationService notificationService;
	private final Clock clock;
	private final AtomicBoolean running = new AtomicBoolean(false);

	@Scheduled(cron = "${transaction.notification.cleanup-cron}", zone = "Asia/Seoul")
	public void notifyDailyCleanup() {
		if (!running.compareAndSet(false, true)) {
			log.warn("미분류 거래 정리 알림 건너뜀 — 이전 실행 진행 중");
			return;
		}
		try {
			LocalDate today = LocalDate.now(clock);
			for (PendingTransactionSummary summary : transactionRepository.findPendingTransactionSummaries()) {
				try {
					notificationService.notifyDailyCleanup(
							summary.getUserId(), summary.getPendingCount(), today);
				} catch (RuntimeException exception) {
					log.warn("미분류 거래 정리 알림 생성 실패: userId={}", summary.getUserId());
				}
			}
		} finally {
			running.set(false);
		}
	}
}
