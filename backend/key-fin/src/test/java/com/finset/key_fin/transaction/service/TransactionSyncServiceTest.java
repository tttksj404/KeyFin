package com.finset.key_fin.transaction.service;

import com.finset.key_fin.account.entity.Account;
import com.finset.key_fin.account.repository.AccountRepository;
import com.finset.key_fin.card.entity.Card;
import com.finset.key_fin.card.repository.CardRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.finance.exception.FinanceErrorCode;
import com.finset.key_fin.link.exception.LinkErrorCode;
import com.finset.key_fin.transaction.client.FinanceAccountTransactionClient;
import com.finset.key_fin.transaction.client.FinanceCardTransactionClient;
import com.finset.key_fin.transaction.dto.finance.response.FinanceAccountTransaction;
import com.finset.key_fin.transaction.dto.finance.response.FinanceCardTransaction;
import com.finset.key_fin.transaction.entity.ConfirmStatus;
import com.finset.key_fin.transaction.entity.ExcludeTag;
import com.finset.key_fin.transaction.entity.Transaction;
import com.finset.key_fin.transaction.entity.TransactionStatus;
import com.finset.key_fin.transaction.entity.TransactionType;
import com.finset.key_fin.transaction.repository.SubcategoryQueryRepository;
import com.finset.key_fin.transaction.repository.TransactionRepository;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.anySet;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
@SuppressWarnings("unchecked")
class TransactionSyncServiceTest {

	private static final long USER_ID = 1L;
	private static final LocalDate START_DATE = LocalDate.of(2026, 9, 14);
	private static final LocalDate END_DATE = LocalDate.of(2026, 9, 15);
	private static final LocalDateTime SYNC_TIME = LocalDateTime.of(2026, 9, 15, 11, 0);

	@Mock
	private UserRepository userRepository;
	@Mock
	private AccountRepository accountRepository;
	@Mock
	private CardRepository cardRepository;
	@Mock
	private TransactionRepository transactionRepository;
	@Mock
	private FinanceAccountTransactionClient accountTransactionClient;
	@Mock
	private FinanceCardTransactionClient cardTransactionClient;
	@Mock
	private TransactionClassificationService classificationService;
	@Mock
	private TransactionSyncWriter syncWriter;
	@Mock
	private SubcategoryQueryRepository subcategoryQueryRepository;

	private TransactionSyncService syncService;
	private User user;

	@BeforeEach
	void setUp() {
		syncService = new TransactionSyncService(
				subcategoryQueryRepository,
				userRepository,
				accountRepository,
				cardRepository,
				transactionRepository,
				accountTransactionClient,
				cardTransactionClient,
				classificationService,
				syncWriter,
				Clock.fixed(
						Instant.parse("2026-09-15T02:00:00Z"),
						ZoneId.of("Asia/Seoul")
				)
		);
		user = User.create("qwer@qwer.com", "password", "김예린");
		ReflectionTestUtils.setField(user, "id", USER_ID);
		user.connectFinance("finance-user-key");
	}

	@Test
	void 관리_계좌와_카드의_신규_거래를_수집해_저장한다() {
		Account account = account(3L, "0016174648358792");
		Card card = card(7L, account);
		FinanceAccountTransaction accountResponse = accountResponse("61", "출금", null);
		FinanceCardTransaction cardResponse = cardResponse("20", "승인");
		Transaction accountTransaction = accountTransaction(account, "61", ExcludeTag.NONE);
		Transaction cardTransaction = cardTransaction(card, "20", TransactionStatus.NORMAL);
		givenCommonAssets(List.of(account), List.of(card));
		given(accountTransactionClient.findTransactions(
				"finance-user-key", account.getFinAccountNo(), START_DATE, END_DATE))
				.willReturn(List.of(accountResponse));
		given(cardTransactionClient.findTransactions(
				"finance-user-key", card.getFinCardNo(), card.getCvc(), START_DATE, END_DATE))
				.willReturn(List.of(cardResponse));
		given(classificationService.fromAccount(user, account, accountResponse)).willReturn(accountTransaction);
		given(classificationService.fromCard(user, card, cardResponse)).willReturn(cardTransaction);

		syncService.sync(USER_ID, START_DATE, END_DATE);

		ArgumentCaptor<List<Transaction>> captor = ArgumentCaptor.forClass(List.class);
		verify(syncWriter).save(org.mockito.ArgumentMatchers.eq(USER_ID), anyList(), captor.capture(), anyMap(), anyMap());
		assertThat(captor.getValue()).containsExactly(accountTransaction, cardTransaction);
		assertThat(account.getBalance()).isEqualTo(990_000L);
		assertThat(account.getBalanceUpdatedAt()).isEqualTo(SYNC_TIME);
	}

	@Test
	void DB와_한번의_응답에_중복된_거래는_건너뛴다() {
		Account account = account(3L, "0016174648358792");
		FinanceAccountTransaction stored = accountResponse("61", "출금", null);
		FinanceAccountTransaction first = accountResponse("62", "출금", null);
		FinanceAccountTransaction duplicate = accountResponse("62", "출금", null);
		Transaction transaction = accountTransaction(account, "62", ExcludeTag.NONE);
		givenCommonAssets(List.of(account), List.of());
		given(accountTransactionClient.findTransactions(
				"finance-user-key", account.getFinAccountNo(), START_DATE, END_DATE))
				.willReturn(List.of(stored, first, duplicate));
		given(transactionRepository.existsByUserIdAndFinTransactionUniqueNo(USER_ID, "61"))
				.willReturn(true);
		given(classificationService.fromAccount(user, account, first)).willReturn(transaction);

		syncService.sync(USER_ID, START_DATE, END_DATE);

		verify(syncWriter).save(USER_ID, List.of(account), List.of(transaction), Map.of(), Map.of());
		verify(classificationService, never()).fromAccount(user, account, stored);
	}

	@Test
	void 관리_자산이_없으면_금융망을_호출하지_않는다() {
		givenCommonAssets(List.of(), List.of());

		syncService.sync(USER_ID, START_DATE, END_DATE);

		verifyNoInteractions(accountTransactionClient, cardTransactionClient, classificationService);
		verify(syncWriter).save(USER_ID, List.of(), List.of(), Map.of(), Map.of());
	}

	@Test
	void SELF_TRANSFER이면_기존_반대편_거래_최신_한건을_재분류한다() {
		Account source = account(3L, "0016174648358792");
		Account counterpart = account(4L, "0204667768182760");
		FinanceAccountTransaction response = accountResponse(
				"62", "입금(이체)", counterpart.getFinAccountNo());
		Transaction current = accountTransaction(source, "62", ExcludeTag.SELF_TRANSFER);
		Transaction existing = accountTransaction(counterpart, "61", ExcludeTag.NONE);
		ReflectionTestUtils.setField(existing, "id", 100L);
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(accountRepository.findByIdAndUserId(source.getId(), USER_ID)).willReturn(Optional.of(source));
		given(accountTransactionClient.findTransactions(
				"finance-user-key", source.getFinAccountNo(), START_DATE, END_DATE))
				.willReturn(List.of(response));
		given(classificationService.fromAccount(user, source, response)).willReturn(current);
		given(accountRepository.findByUserIdAndFinAccountNoAndManagedTrue(
				USER_ID, counterpart.getFinAccountNo())).willReturn(Optional.of(counterpart));
		given(transactionRepository
				.findFirstByUserIdAndAccountIdAndTransactionDateAndTransactionTimeAndAmountAndStatusAndExcludeTagNotAndConfirmStatusInOrderByIdDesc(
						USER_ID,
						counterpart.getId(),
						current.getTransactionDate(),
						current.getTransactionTime(),
						current.getAmount(),
						TransactionStatus.NORMAL,
						ExcludeTag.SELF_TRANSFER,
						List.of(ConfirmStatus.PENDING, ConfirmStatus.AUTO)))
				.willReturn(Optional.of(existing));

		syncService.syncNewlyManagedAccountHistory(
				USER_ID, source.getId(), START_DATE, END_DATE);

		assertThat(existing.getExcludeTag()).isEqualTo(ExcludeTag.SELF_TRANSFER);
		assertThat(existing.getConfirmStatus()).isEqualTo(ConfirmStatus.CONFIRMED);
		ArgumentCaptor<List<Transaction>> captor = ArgumentCaptor.forClass(List.class);
		ArgumentCaptor<Map<Long, Transaction>> reclassifiedCaptor = ArgumentCaptor.forClass(Map.class);
		verify(syncWriter).saveHistory(org.mockito.ArgumentMatchers.eq(USER_ID), anyList(), captor.capture(), reclassifiedCaptor.capture(), anyMap());
		assertThat(captor.getValue()).containsExactly(current);
		assertThat(reclassifiedCaptor.getValue()).containsEntry(existing.getId(), existing);
	}

	@Test
	void 일반_수집에서는_SELF_TRANSFER의_기존_반대편_거래를_재분류하지_않는다() {
		Account source = account(3L, "0016174648358792");
		FinanceAccountTransaction response = accountResponse(
				"62", "입금(이체)", "0204667768182760");
		Transaction current = accountTransaction(source, "62", ExcludeTag.SELF_TRANSFER);
		givenCommonAssets(List.of(source), List.of());
		given(accountTransactionClient.findTransactions(
				"finance-user-key", source.getFinAccountNo(), START_DATE, END_DATE))
				.willReturn(List.of(response));
		given(classificationService.fromAccount(user, source, response)).willReturn(current);

		syncService.sync(USER_ID, START_DATE, END_DATE);

		verify(accountRepository, never())
				.findByUserIdAndFinAccountNoAndManagedTrue(any(), any());
		verify(syncWriter).save(USER_ID, List.of(source), List.of(current), Map.of(), Map.of());
	}

	@Test
	void 카드_조회가_실패하면_앞서_변환한_계좌_거래도_저장하지_않는다() {
		Account account = account(3L, "0016174648358792");
		Card card = card(7L, account);
		FinanceAccountTransaction response = accountResponse("61", "출금", null);
		Transaction transaction = accountTransaction(account, "61", ExcludeTag.NONE);
		givenCommonAssets(List.of(account), List.of(card));
		given(accountTransactionClient.findTransactions(
				"finance-user-key", account.getFinAccountNo(), START_DATE, END_DATE))
				.willReturn(List.of(response));
		given(classificationService.fromAccount(user, account, response)).willReturn(transaction);
		given(cardTransactionClient.findTransactions(
				"finance-user-key", card.getFinCardNo(), card.getCvc(), START_DATE, END_DATE))
				.willThrow(new BusinessException(FinanceErrorCode.SERVICE_UNAVAILABLE));

		assertThatThrownBy(() -> syncService.sync(USER_ID, START_DATE, END_DATE))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(FinanceErrorCode.SERVICE_UNAVAILABLE));
		verifyNoInteractions(syncWriter);
	}

	@Test
	void 금융망이_연결되지_않은_사용자는_수집하지_않는다() {
		User disconnectedUser = User.create("qwer@qwer.com", "password", "김예린");
		ReflectionTestUtils.setField(disconnectedUser, "id", USER_ID);
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(disconnectedUser));

		assertThatThrownBy(() -> syncService.sync(USER_ID, START_DATE, END_DATE))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(LinkErrorCode.FINANCE_NOT_CONNECTED));
		verifyNoInteractions(accountTransactionClient, cardTransactionClient);
	}

	@Test
	void 관리_계좌_하나의_거래를_동기화한다() {
		Account account = account(3L, "0016174648358792");
		FinanceAccountTransaction response = accountResponse("61", "출금", null);
		Transaction transaction = accountTransaction(account, "61", ExcludeTag.NONE);
		given(accountTransactionClient.findTransactions(
				"finance-user-key", account.getFinAccountNo(), START_DATE, END_DATE))
				.willReturn(List.of(response));
		given(classificationService.fromAccount(user, account, response)).willReturn(transaction);

		syncService.syncAccountTransactions(user, account, START_DATE, END_DATE);

		verify(syncWriter).save(USER_ID, List.of(account), List.of(transaction), Map.of(), Map.of());
		verifyNoInteractions(cardTransactionClient);
	}

	@Test
	void 관리_카드_하나의_거래를_동기화한다() {
		Account account = account(3L, "0016174648358792");
		Card card = card(7L, account);
		FinanceCardTransaction response = cardResponse("20", "승인");
		Transaction transaction = cardTransaction(card, "20", TransactionStatus.NORMAL);
		given(cardTransactionClient.findTransactions(
				"finance-user-key", card.getFinCardNo(), card.getCvc(), START_DATE, END_DATE))
				.willReturn(List.of(response));
		given(classificationService.fromCard(user, card, response)).willReturn(transaction);

		syncService.syncCardTransactions(user, card, START_DATE, END_DATE);

		verify(syncWriter).save(USER_ID, List.of(), List.of(transaction), Map.of(), Map.of());
		verifyNoInteractions(accountTransactionClient);
		assertThat(account.getBalance()).isEqualTo(1_000_000L);
	}

	@Test
	void 승인으로_수집한_카드_거래가_취소로_오면_CANCELED로_바꾸고_봉투_변경을_알린다() {
		Account account = account(3L, "0016174648358792");
		Card card = card(7L, account);
		FinanceCardTransaction revoked = cardResponse("20", "취소");
		Transaction stored = cardTransaction(card, "20", TransactionStatus.NORMAL);
		ReflectionTestUtils.setField(stored, "id", 981L);
		given(cardTransactionClient.findTransactions(
				"finance-user-key", card.getFinCardNo(), card.getCvc(), START_DATE, END_DATE))
				.willReturn(List.of(revoked));
		given(transactionRepository.findByUserIdAndFinTransactionUniqueNo(USER_ID, "20"))
				.willReturn(Optional.of(stored));
		given(classificationService.isCardCanceled(revoked)).willReturn(true);
		given(subcategoryQueryRepository.findEnvelopeId(203)).willReturn(Optional.of(2));

		syncService.syncCardTransactions(user, card, START_DATE, END_DATE);

		assertThat(stored.getStatus()).isEqualTo(TransactionStatus.CANCELED);
		assertThat(stored.getAmount()).isEqualTo(20_000L);
		assertThat(stored.getSubcategoryId()).isEqualTo(203);
		verify(syncWriter).save(USER_ID, List.of(), List.of(), Map.of(981L, stored), Map.of(2, 20_000L));
		verify(classificationService, never()).fromCard(user, card, revoked);
	}

	@Test
	void 이미_CANCELED인_카드_거래를_다시_받아도_저장과_알림이_없다() {
		Account account = account(3L, "0016174648358792");
		Card card = card(7L, account);
		FinanceCardTransaction revoked = cardResponse("20", "취소");
		Transaction stored = cardTransaction(card, "20", TransactionStatus.CANCELED);
		given(cardTransactionClient.findTransactions(
				"finance-user-key", card.getFinCardNo(), card.getCvc(), START_DATE, END_DATE))
				.willReturn(List.of(revoked));
		given(transactionRepository.findByUserIdAndFinTransactionUniqueNo(USER_ID, "20"))
				.willReturn(Optional.of(stored));

		syncService.syncCardTransactions(user, card, START_DATE, END_DATE);

		verify(syncWriter).save(USER_ID, List.of(), List.of(), Map.of(), Map.of());
		verifyNoInteractions(subcategoryQueryRepository);
	}

	@Test
	void 승인_상태로_다시_받은_카드_거래는_건너뛴다() {
		Account account = account(3L, "0016174648358792");
		Card card = card(7L, account);
		FinanceCardTransaction approved = cardResponse("20", "승인");
		Transaction stored = cardTransaction(card, "20", TransactionStatus.NORMAL);
		given(cardTransactionClient.findTransactions(
				"finance-user-key", card.getFinCardNo(), card.getCvc(), START_DATE, END_DATE))
				.willReturn(List.of(approved));
		given(transactionRepository.findByUserIdAndFinTransactionUniqueNo(USER_ID, "20"))
				.willReturn(Optional.of(stored));

		syncService.syncCardTransactions(user, card, START_DATE, END_DATE);

		assertThat(stored.getStatus()).isEqualTo(TransactionStatus.NORMAL);
		verify(syncWriter).save(USER_ID, List.of(), List.of(), Map.of(), Map.of());
		verifyNoInteractions(subcategoryQueryRepository);
	}

	private void givenCommonAssets(List<Account> accounts, List<Card> cards) {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(accountRepository.findAllByUserIdAndManagedTrueOrderByIdAsc(USER_ID)).willReturn(accounts);
		given(cardRepository.findAllByUserIdAndManagedTrueOrderByIdAsc(USER_ID)).willReturn(cards);
	}

	private Account account(long id, String accountNo) {
		Account account = Account.sync(
				user,
				accountNo,
				"001",
				"한국은행",
				1_000_000L,
				LocalDateTime.of(2026, 9, 15, 9, 0)
		);
		account.link();
		ReflectionTestUtils.setField(account, "id", id);
		return account;
	}

	private Card card(long id, Account account) {
		Card card = Card.sync(
				user,
				"1005518816096479",
				"725",
				"1005",
				"신한 TRAVEL 카드",
				account
		);
		card.link();
		ReflectionTestUtils.setField(card, "id", id);
		return card;
	}

	private FinanceAccountTransaction accountResponse(
			String transactionNumber,
			String transactionTypeName,
			String counterpartAccountNo
	) {
		return new FinanceAccountTransaction(
				transactionNumber,
				"20260915",
				"103000",
				"2",
				transactionTypeName,
				counterpartAccountNo,
				10_000L,
				990_000L,
				"계좌 거래",
				null
		);
	}

	private FinanceCardTransaction cardResponse(String transactionNumber, String cardStatus) {
		return new FinanceCardTransaction(
				transactionNumber,
				"CG-3fa85f6425e811e",
				"주유",
				1L,
				"주유소",
				"20260915",
				"103000",
				20_000L,
				cardStatus,
				"N",
				"미결제"
		);
	}

	private Transaction accountTransaction(Account account, String transactionNumber, ExcludeTag excludeTag) {
		ConfirmStatus confirmStatus = ConfirmStatus.PENDING;
		if (excludeTag == ExcludeTag.SELF_TRANSFER) {
			confirmStatus = ConfirmStatus.CONFIRMED;
		}
		return Transaction.collectAccount(
				user,
				account.getId(),
				transactionNumber,
				TransactionType.TRANSFER,
				"계좌 거래",
				10_000L,
				LocalDate.of(2026, 9, 15),
				LocalTime.of(10, 30),
				confirmStatus,
				excludeTag
		);
	}

	private Transaction cardTransaction(Card card, String transactionNumber, TransactionStatus status) {
		return Transaction.collectCard(
				user,
				card.getId(),
				transactionNumber,
				1L,
				"주유소",
				20_000L,
				LocalDate.of(2026, 9, 15),
				LocalTime.of(10, 30),
				203,
				ConfirmStatus.AUTO,
				status
		);
	}
}
