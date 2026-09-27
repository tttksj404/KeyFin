package com.finset.key_fin.transaction.service;

import com.finset.key_fin.account.entity.Account;
import com.finset.key_fin.account.repository.AccountRepository;
import com.finset.key_fin.transaction.entity.Transaction;
import com.finset.key_fin.transaction.entity.ConfirmStatus;
import com.finset.key_fin.transaction.entity.TransactionStatus;
import com.finset.key_fin.transaction.entity.TransactionType;
import com.finset.key_fin.transaction.event.AccountWithdrawn;
import com.finset.key_fin.transaction.event.PendingTransactionSaved;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.budget.event.EnvelopeSpendingChanged;
import com.finset.key_fin.transaction.repository.SubcategoryQueryRepository;
import com.finset.key_fin.transaction.repository.TransactionRepository;
import com.finset.key_fin.room.service.RoomStickerService;
import com.finset.key_fin.user.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.context.ApplicationEventPublisher;

import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.Optional;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoMoreInteractions;
import static org.mockito.BDDMockito.given;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class TransactionSyncWriterTest {

	@Mock
	private AccountRepository accountRepository;

	@Mock
	private TransactionRepository transactionRepository;
	@Mock private UserRepository users;
	@Mock private RoomStickerService stickers;
	@Mock private SubcategoryQueryRepository subcategories;

	@Mock
	private ApplicationEventPublisher events;

	@InjectMocks
	private TransactionSyncWriter syncWriter;

	@BeforeEach
	void setUp() {
		when(users.findActiveByIdForUpdate(1L)).thenReturn(Optional.of(mock(User.class)));
	}

	@Test
	void 거래와_계좌_잔액을_함께_저장한다() {
		Account account = mock(Account.class);
		Transaction reclassifiedTransaction = mock(Transaction.class);
		Transaction newTransaction = mock(Transaction.class);

		syncWriter.save(
				1L,
				List.of(account),
				List.of(newTransaction),
				Map.of(10L, reclassifiedTransaction),
				Map.of()
		);

		verify(transactionRepository).saveAll(List.of(reclassifiedTransaction, newTransaction));
		verify(accountRepository).saveAll(List.of(account));
		verify(stickers).synchronize(1L);
	}

	@Test
	void 신규_미분류_지출_거래마다_이벤트를_발행한다() {
		User user = mock(User.class);
		given(user.getId()).willReturn(1L);
		Transaction first = pendingCardTransaction(user, 10L, "메가커피 역삼점", 4_500L);
		Transaction second = pendingCardTransaction(user, 11L, "김밥천국", 9_000L);

		syncWriter.save(1L, List.of(), List.of(first, second), Map.of(), Map.of());

		verify(events).publishEvent(new PendingTransactionSaved(1L, 10L, "메가커피 역삼점", 4_500L));
		verify(events).publishEvent(new PendingTransactionSaved(1L, 11L, "김밥천국", 9_000L));
	}

	@Test
	void 과거_이력_적재에는_즉시_알림_이벤트를_발행하지_않는다() {
		Transaction transaction = mock(Transaction.class);

		syncWriter.saveHistory(1L, List.of(), List.of(transaction), Map.of(), Map.of());

		verify(transactionRepository).saveAll(List.of(transaction));
		verify(events, never()).publishEvent(any());
	}

	private Transaction pendingCardTransaction(User user, long id, String merchantName, long amount) {
		Transaction transaction = mock(Transaction.class);
		given(transaction.getUser()).willReturn(user);
		given(transaction.getId()).willReturn(id);
		given(transaction.getMerchantNameRaw()).willReturn(merchantName);
		given(transaction.getAmount()).willReturn(amount);
		given(transaction.getConfirmStatus()).willReturn(ConfirmStatus.PENDING);
		given(transaction.getStatus()).willReturn(TransactionStatus.NORMAL);
		given(transaction.getTransactionType()).willReturn(TransactionType.CARD);
		return transaction;
	}

	@Test
	void 입금_거래에는_미분류_이벤트를_발행하지_않는다() {
		Transaction transaction = mock(Transaction.class);
		given(transaction.getConfirmStatus()).willReturn(ConfirmStatus.PENDING);
		given(transaction.getStatus()).willReturn(TransactionStatus.NORMAL);
		given(transaction.getTransactionType()).willReturn(TransactionType.DEPOSIT);

		syncWriter.save(1L, List.of(), List.of(transaction), Map.of(), Map.of());

		verify(events, never()).publishEvent(any());
	}

	@Test
	void 계좌_출금_거래는_계좌마다_한_번씩_AccountWithdrawn을_발행한다() {
		User user = mock(User.class);
		given(user.getId()).willReturn(1L);
		Transaction first = accountTransaction(20L, TransactionType.WITHDRAW);
		Transaction second = accountTransaction(20L, TransactionType.TRANSFER);
		Transaction third = accountTransaction(21L, TransactionType.WITHDRAW);
		given(first.getUser()).willReturn(user);
		given(third.getUser()).willReturn(user);

		syncWriter.save(1L, List.of(), List.of(first, second, third), Map.of(), Map.of());

		verify(events, times(1)).publishEvent(new AccountWithdrawn(1L, 20L));
		verify(events, times(1)).publishEvent(new AccountWithdrawn(1L, 21L));
	}

	@Test
	void 카드_결제와_입금에는_AccountWithdrawn을_발행하지_않는다() {
		Transaction card = mock(Transaction.class);
		Transaction deposit = mock(Transaction.class);
		given(deposit.getAccountId()).willReturn(20L);
		given(deposit.getStatus()).willReturn(TransactionStatus.NORMAL);
		given(deposit.getTransactionType()).willReturn(TransactionType.DEPOSIT);

		syncWriter.save(1L, List.of(), List.of(card, deposit), Map.of(), Map.of());

		verify(events, never()).publishEvent(any(AccountWithdrawn.class));
	}

	@Test
	void 자동_분류된_신규_거래는_봉투마다_한_번씩_EnvelopeSpendingChanged를_발행한다() {
		Transaction first = autoClassifiedCardTransaction(101);
		Transaction second = autoClassifiedCardTransaction(103);
		Transaction other = autoClassifiedCardTransaction(602);
		given(subcategories.findEnvelopeId(101)).willReturn(Optional.of(1));
		given(subcategories.findEnvelopeId(103)).willReturn(Optional.of(1));
		given(subcategories.findEnvelopeId(602)).willReturn(Optional.of(6));

		syncWriter.save(1L, List.of(), List.of(first, second, other), Map.of(), Map.of());

		verify(events).publishEvent(new EnvelopeSpendingChanged(1L, 1));
		verify(events).publishEvent(new EnvelopeSpendingChanged(1L, 6));
		verify(events, times(2)).publishEvent(any(EnvelopeSpendingChanged.class));
	}

	@Test
	void 미분류_거래와_취소_거래에는_EnvelopeSpendingChanged를_발행하지_않는다() {
		User user = mock(User.class);
		given(user.getId()).willReturn(1L);
		Transaction pending = pendingCardTransaction(user, 10L, "메가커피 역삼점", 4_500L);
		Transaction canceled = mock(Transaction.class);
		given(canceled.getStatus()).willReturn(TransactionStatus.CANCELED);

		syncWriter.save(1L, List.of(), List.of(pending, canceled), Map.of(), Map.of());

		verify(events, never()).publishEvent(any(EnvelopeSpendingChanged.class));
		verify(subcategories, never()).findEnvelopeId(any(Integer.class));
	}

	@Test
	void 전달받은_봉투는_신규_거래의_봉투와_합쳐_한_번씩_발행한다() {
		Transaction auto = autoClassifiedCardTransaction(101);
		given(subcategories.findEnvelopeId(101)).willReturn(Optional.of(1));

		syncWriter.save(1L, List.of(), List.of(auto), Map.of(), Map.of(4, 12_000L));

		verify(events).publishEvent(new EnvelopeSpendingChanged(1L, 1, null));
		verify(events).publishEvent(new EnvelopeSpendingChanged(1L, 4, 12_000L));
		verify(events, times(2)).publishEvent(any(EnvelopeSpendingChanged.class));
	}

	@Test
	void 과거_이력_적재는_전달받은_봉투만_발행한다() {
		Transaction transaction = mock(Transaction.class);

		syncWriter.saveHistory(1L, List.of(), List.of(transaction), Map.of(), Collections.singletonMap(4, null));

		verify(events).publishEvent(new EnvelopeSpendingChanged(1L, 4, null));
		verifyNoMoreInteractions(events);
		verify(subcategories, never()).findEnvelopeId(any(Integer.class));
	}

	private Transaction autoClassifiedCardTransaction(int subcategoryId) {
		Transaction transaction = mock(Transaction.class);
		given(transaction.getStatus()).willReturn(TransactionStatus.NORMAL);
		given(transaction.getConfirmStatus()).willReturn(ConfirmStatus.AUTO);
		given(transaction.getSubcategoryId()).willReturn(subcategoryId);
		given(transaction.getAccountId()).willReturn(null);
		return transaction;
	}

	private Transaction accountTransaction(long accountId, TransactionType type) {
		Transaction transaction = mock(Transaction.class);
		given(transaction.getAccountId()).willReturn(accountId);
		given(transaction.getStatus()).willReturn(TransactionStatus.NORMAL);
		given(transaction.getTransactionType()).willReturn(type);
		return transaction;
	}
}
