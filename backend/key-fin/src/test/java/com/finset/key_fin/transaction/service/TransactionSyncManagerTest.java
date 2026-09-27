package com.finset.key_fin.transaction.service;

import com.finset.key_fin.account.entity.Account;
import com.finset.key_fin.account.repository.AccountRepository;
import com.finset.key_fin.card.entity.Card;
import com.finset.key_fin.card.repository.CardRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.finance.exception.FinanceErrorCode;
import com.finset.key_fin.transaction.entity.TransactionAssetType;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class TransactionSyncManagerTest {

	private static final long USER_ID = 1L;
	private static final LocalDateTime SYNC_TIME = LocalDateTime.of(2026, 9, 15, 10, 30);
	private static final LocalDate TODAY = SYNC_TIME.toLocalDate();
	private static final LocalDate START_DATE = TODAY.minusDays(1);

	@Mock
	private UserRepository userRepository;
	@Mock
	private AccountRepository accountRepository;
	@Mock
	private CardRepository cardRepository;
	@Mock
	private TransactionSyncService transactionSyncService;
	@Mock
	private TransactionSyncStateService syncStateService;

	private TransactionSyncManager syncManager;
	private User user;
	private Account account;
	private Card card;

	@BeforeEach
	void setUp() {
		syncManager = new TransactionSyncManager(
				userRepository,
				accountRepository,
				cardRepository,
				transactionSyncService,
				syncStateService
		);
		user = User.create("qwer@qwer.com", "password", "김예린");
		ReflectionTestUtils.setField(user, "id", USER_ID);
		user.connectFinance("finance-user-key");
		account = managedAccount(3L);
		card = managedCard(7L, account);
	}

	@Test
	void 사용자의_관리_계좌와_카드를_하나씩_동기화한다() {
		givenSyncTargets();
		givenSyncStartDate(TransactionAssetType.ACCOUNT, account.getId());
		givenSyncStartDate(TransactionAssetType.CARD, card.getId());

		syncManager.syncUser(USER_ID, SYNC_TIME);

		verify(transactionSyncService).syncAccountTransactions(user, account, START_DATE, TODAY);
		verify(transactionSyncService).syncCardTransactions(user, card, START_DATE, TODAY);
		verify(syncStateService).recordSyncSuccess(
				user, TransactionAssetType.ACCOUNT, account.getId(), SYNC_TIME);
		verify(syncStateService).recordSyncSuccess(
				user, TransactionAssetType.CARD, card.getId(), SYNC_TIME);
	}

	@Test
	void 계좌_동기화이_실패해도_카드_동기화을_계속한다() {
		givenSyncTargets();
		givenSyncStartDate(TransactionAssetType.ACCOUNT, account.getId());
		givenSyncStartDate(TransactionAssetType.CARD, card.getId());
		doThrow(new BusinessException(FinanceErrorCode.SERVICE_UNAVAILABLE))
				.when(transactionSyncService)
				.syncAccountTransactions(user, account, START_DATE, TODAY);

		syncManager.syncUser(USER_ID, SYNC_TIME);

		verify(syncStateService, never()).recordSyncSuccess(
				user, TransactionAssetType.ACCOUNT, account.getId(), SYNC_TIME);
		verify(transactionSyncService).syncCardTransactions(user, card, START_DATE, TODAY);
		verify(syncStateService).recordSyncSuccess(
				user, TransactionAssetType.CARD, card.getId(), SYNC_TIME);
	}

	@Test
	void 금융_사용자_키가_무효하면_해당_사용자의_남은_동기화을_중단한다() {
		givenSyncTargets();
		givenSyncStartDate(TransactionAssetType.ACCOUNT, account.getId());
		doThrow(new BusinessException(FinanceErrorCode.USER_KEY_INVALID))
				.when(transactionSyncService)
				.syncAccountTransactions(user, account, START_DATE, TODAY);

		syncManager.syncUser(USER_ID, SYNC_TIME);

		verify(transactionSyncService, never()).syncCardTransactions(
				user, card, START_DATE, TODAY);
		verify(syncStateService, never()).recordSyncSuccess(
				user, TransactionAssetType.ACCOUNT, account.getId(), SYNC_TIME);
	}

	private void givenSyncTargets() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(accountRepository.findAllByUserIdAndManagedTrueOrderByIdAsc(USER_ID))
				.willReturn(List.of(account));
		given(cardRepository.findAllByUserIdAndManagedTrueOrderByIdAsc(USER_ID))
				.willReturn(List.of(card));
	}

	private void givenSyncStartDate(TransactionAssetType assetType, long assetId) {
		given(syncStateService.calculateSyncStartDate(
				USER_ID, assetType, assetId, TODAY)).willReturn(START_DATE);
	}

	private Account managedAccount(long id) {
		Account account = Account.sync(
				user,
				"0016174648358792",
				"001",
				"한국은행",
				1_000_000L,
				LocalDateTime.of(2026, 9, 15, 9, 0)
		);
		account.link();
		ReflectionTestUtils.setField(account, "id", id);
		return account;
	}

	private Card managedCard(long id, Account withdrawalAccount) {
		Card card = Card.sync(
				user,
				"1005518816096479",
				"725",
				"1005",
				"신한 TRAVEL 카드",
				withdrawalAccount
		);
		card.link();
		ReflectionTestUtils.setField(card, "id", id);
		return card;
	}
}

