package com.finset.key_fin.transaction.service;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.exception.CommonErrorCode;
import com.finset.key_fin.notification.entity.NotificationType;
import com.finset.key_fin.notification.service.NotificationService;
import com.finset.key_fin.transaction.event.PendingTransactionSaved;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class TransactionNotificationServiceTest {

	private final NotificationService notifications = mock(NotificationService.class);
	private final TransactionNotificationCooldownService cooldown = mock(TransactionNotificationCooldownService.class);
	private final TransactionNotificationService service =
			new TransactionNotificationService(notifications, cooldown);

	@Test
	void 신규_미분류_거래마다_가맹점과_금액을_담아_코칭_알림을_생성한다() {
		service.notifyPendingTransaction(
				new PendingTransactionSaved(1L, 10L, "메가커피 역삼점", 4_500L));

		verify(notifications).create(
				1L, NotificationType.COACHING,
				"새로 정리할 거래가 있어요",
				"메가커피 역삼점 4,500원을 분류해 주세요.",
				"10", true);
	}

	@Test
	void 가맹점명이_없으면_금액만으로_알림을_생성한다() {
		service.notifyPendingTransaction(new PendingTransactionSaved(1L, 11L, null, 120_000L));

		verify(notifications).create(
				1L, NotificationType.COACHING,
				"새로 정리할 거래가 있어요",
				"120,000원 거래를 분류해 주세요.",
				"11", true);
	}

	@Test
	void 즉시_알림은_제한하지_않고_거래마다_생성한다() {
		service.notifyPendingTransaction(new PendingTransactionSaved(1L, 10L, "메가커피", 4_500L));
		service.notifyPendingTransaction(new PendingTransactionSaved(1L, 11L, "김밥천국", 9_000L));

		verify(notifications).create(1L, NotificationType.COACHING,
				"새로 정리할 거래가 있어요", "메가커피 4,500원을 분류해 주세요.", "10", true);
		verify(notifications).create(1L, NotificationType.COACHING,
				"새로 정리할 거래가 있어요", "김밥천국 9,000원을 분류해 주세요.", "11", true);
	}

	@Test
	void 한_건의_알림_생성_실패가_동기화를_중단시키지_않는다() {
		doThrow(new BusinessException(CommonErrorCode.INVALID_INPUT_VALUE))
				.when(notifications).create(anyLong(), any(), anyString(), anyString(), any(), anyBoolean());

		assertThatCode(() -> service.notifyPendingTransaction(
				new PendingTransactionSaved(1L, 10L, "메가커피", 4_500L)))
				.doesNotThrowAnyException();
	}

	@Test
	void 미분류_거래가_남아있으면_일괄_정리_알림을_생성한다() {
		LocalDate date = LocalDate.of(2026, 9, 18);
		when(cooldown.acquireDailyCleanup(1L, date)).thenReturn(true);

		service.notifyDailyCleanup(1L, 4L, date);

		verify(notifications).create(
				1L, NotificationType.CLEANUP,
				"오늘의 소비를 정리해 볼까요?",
				"아직 분류하지 않은 거래가 4건 있어요.",
				null, true);
	}

	@Test
	void 같은_날_두_번째_정리_알림은_생성하지_않는다() {
		LocalDate date = LocalDate.of(2026, 9, 18);
		when(cooldown.acquireDailyCleanup(1L, date)).thenReturn(false);

		service.notifyDailyCleanup(1L, 4L, date);

		verify(notifications, never()).create(anyLong(), any(), anyString(), anyString(), any(), anyBoolean());
	}
}
