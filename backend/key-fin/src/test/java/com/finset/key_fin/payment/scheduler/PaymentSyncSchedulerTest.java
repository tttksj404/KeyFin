package com.finset.key_fin.payment.scheduler;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.finance.exception.FinanceErrorCode;
import com.finset.key_fin.payment.service.CardBillingSyncService;
import com.finset.key_fin.payment.service.SubscriptionSyncService;
import com.finset.key_fin.payment.service.TransferProposalService;
import com.finset.key_fin.payment.service.TransferService;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.repository.UserRepository;

class PaymentSyncSchedulerTest {

	private final UserRepository userRepository = mock(UserRepository.class);
	private final SubscriptionSyncService subscriptionSyncService = mock(SubscriptionSyncService.class);
	private final CardBillingSyncService cardBillingSyncService = mock(CardBillingSyncService.class);
	private final TransferProposalService transferProposalService = mock(TransferProposalService.class);
	private final TransferService transferService = mock(TransferService.class);
	private final PaymentSyncScheduler scheduler =
			new PaymentSyncScheduler(userRepository, subscriptionSyncService, cardBillingSyncService, transferProposalService, transferService);

	@Test
	@DisplayName("연결된 사용자마다 구독·카드 청구를 동기화하고, 한 사용자의 실패가 다음 사용자를 막지 않는다")
	void continuesAfterFailure() {
		User first = mock(User.class);
		User second = mock(User.class);
		when(first.getId()).thenReturn(1L);
		when(second.getId()).thenReturn(2L);
		when(userRepository.findAllByFinUserKeyIsNotNullAndDeletedAtIsNull()).thenReturn(List.of(first, second));
		doThrow(new BusinessException(FinanceErrorCode.USER_KEY_INVALID)).when(subscriptionSyncService).sync(1L);

		scheduler.syncAll();

		verify(subscriptionSyncService).sync(1L);
		verify(subscriptionSyncService).sync(2L);
		verify(cardBillingSyncService).sync(2L);
		assertThat(scheduler.syncOne(2L)).isTrue();
		assertThat(scheduler.syncOne(1L)).isFalse();
	}

	@Test
	@DisplayName("구독 동기화가 실패한 사용자는 카드 청구 동기화도 건너뛴다")
	void skipsBillingWhenSubscriptionFails() {
		doThrow(new IllegalStateException("boom")).when(subscriptionSyncService).sync(anyLong());

		assertThat(scheduler.syncOne(7L)).isFalse();
		verify(cardBillingSyncService, org.mockito.Mockito.never()).sync(anyLong());
	}
}
