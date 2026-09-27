package com.finset.key_fin.transaction.scheduler;

import com.finset.key_fin.transaction.repository.PendingTransactionSummary;
import com.finset.key_fin.transaction.repository.TransactionRepository;
import com.finset.key_fin.transaction.service.TransactionNotificationService;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.List;

import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class PendingTransactionNotificationSchedulerTest {

	private final TransactionRepository transactionRepository = mock(TransactionRepository.class);
	private final TransactionNotificationService notificationService = mock(TransactionNotificationService.class);
	private final Clock clock = Clock.fixed(
			Instant.parse("2026-09-18T12:00:00Z"), ZoneId.of("Asia/Seoul"));

	@Test
	void 미분류_거래가_있는_사용자에게_일괄_정리_알림을_요청한다() {
		PendingTransactionSummary first = summary(1L, 3L);
		PendingTransactionSummary second = summary(2L, 1L);
		when(transactionRepository.findPendingTransactionSummaries())
				.thenReturn(List.of(first, second));
		PendingTransactionNotificationScheduler scheduler = scheduler();

		scheduler.notifyDailyCleanup();

		LocalDate date = LocalDate.of(2026, 9, 18);
		verify(notificationService).notifyDailyCleanup(1L, 3L, date);
		verify(notificationService).notifyDailyCleanup(2L, 1L, date);
	}

	@Test
	void 한_사용자_알림이_실패해도_다음_사용자를_계속한다() {
		PendingTransactionSummary first = summary(1L, 3L);
		PendingTransactionSummary second = summary(2L, 1L);
		when(transactionRepository.findPendingTransactionSummaries())
				.thenReturn(List.of(first, second));
		doThrow(new IllegalStateException("failed"))
				.when(notificationService).notifyDailyCleanup(
						1L, 3L, LocalDate.of(2026, 9, 18));

		scheduler().notifyDailyCleanup();

		verify(notificationService).notifyDailyCleanup(
				2L, 1L, LocalDate.of(2026, 9, 18));
	}

	private PendingTransactionNotificationScheduler scheduler() {
		return new PendingTransactionNotificationScheduler(
				transactionRepository, notificationService, clock);
	}

	private PendingTransactionSummary summary(long userId, long count) {
		PendingTransactionSummary summary = mock(PendingTransactionSummary.class);
		when(summary.getUserId()).thenReturn(userId);
		when(summary.getPendingCount()).thenReturn(count);
		return summary;
	}
}
