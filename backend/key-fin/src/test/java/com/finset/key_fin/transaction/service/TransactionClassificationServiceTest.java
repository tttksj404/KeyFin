package com.finset.key_fin.transaction.service;

import com.finset.key_fin.account.entity.Account;
import com.finset.key_fin.account.repository.AccountRepository;
import com.finset.key_fin.card.entity.Card;
import com.finset.key_fin.card.repository.CardRepository;
import com.finset.key_fin.payment.entity.CardBilling;
import com.finset.key_fin.payment.repository.CardBillingRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.finance.exception.FinanceErrorCode;
import com.finset.key_fin.transaction.dto.finance.response.FinanceAccountTransaction;
import com.finset.key_fin.transaction.dto.finance.response.FinanceCardTransaction;
import com.finset.key_fin.transaction.entity.ConfirmStatus;
import com.finset.key_fin.transaction.entity.ExcludeTag;
import com.finset.key_fin.transaction.entity.Transaction;
import com.finset.key_fin.transaction.entity.TransactionStatus;
import com.finset.key_fin.transaction.entity.TransactionType;
import com.finset.key_fin.transaction.repository.MerchantClassification;
import com.finset.key_fin.transaction.repository.MerchantClassificationRepository;
import com.finset.key_fin.user.entity.User;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;

@ExtendWith(MockitoExtension.class)
class TransactionClassificationServiceTest {

	private static final long USER_ID = 1L;
	private static final long ACCOUNT_ID = 3L;
	private static final long CARD_ID = 7L;

	@Mock
	private AccountRepository accountRepository;

	@Mock
	private MerchantClassificationRepository merchantClassificationRepository;

	@Mock
	private CardRepository cardRepository;

	@Mock
	private CardBillingRepository cardBillingRepository;

	private TransactionClassificationService transactionClassificationService;
	private User user;
	private Account account;
	private Card card;

	@BeforeEach
	void setUp() {
		transactionClassificationService = new TransactionClassificationService(
				accountRepository, merchantClassificationRepository, cardRepository, cardBillingRepository);
		user = User.create("qwer@qwer.com", "password", "김예린");
		ReflectionTestUtils.setField(user, "id", USER_ID);
		account = Account.sync(user, "0016174648358792", "001", "한국은행", 1_000_000L,
				java.time.LocalDateTime.of(2026, 9, 14, 12, 0));
		ReflectionTestUtils.setField(account, "id", ACCOUNT_ID);
		card = Card.sync(user, "1005518816096479", "725", "1005", "신한 TRAVEL 카드", account);
		ReflectionTestUtils.setField(card, "id", CARD_ID);
	}

	@Test
	void 일반_입금은_AUTO로_변환한다() {
		Transaction transaction = transactionClassificationService.fromAccount(
				user, account, accountTransaction("1", "입금", null)
		);

		assertThat(transaction.getTransactionType()).isEqualTo(TransactionType.DEPOSIT);
		assertThat(transaction.getConfirmStatus()).isEqualTo(ConfirmStatus.AUTO);
		assertThat(transaction.getExcludeTag()).isEqualTo(ExcludeTag.NONE);
		assertCommonAccountFields(transaction);
	}

	@Test
	void 일반_출금은_PENDING으로_변환한다() {
		Transaction transaction = transactionClassificationService.fromAccount(
				user, account, accountTransaction("2", "출금", null)
		);

		assertThat(transaction.getTransactionType()).isEqualTo(TransactionType.WITHDRAW);
		assertThat(transaction.getConfirmStatus()).isEqualTo(ConfirmStatus.PENDING);
		assertThat(transaction.getExcludeTag()).isEqualTo(ExcludeTag.NONE);
	}

	@Test
	void 청구서와_계좌_금액_출금일이_맞는_출금은_CARD_BILL로_확정한다() {
		card.updateWithdrawalWeekday(1);
		CardBilling billing = CardBilling.sync(CARD_ID, LocalDate.of(2026, 9, 14), 10_000L, false, null);
		given(cardRepository.findAllByUserIdAndManagedTrueAndWithdrawalAccountId(USER_ID, ACCOUNT_ID)).willReturn(List.of(card));
		given(cardBillingRepository.findAllByCardIdInAndTotalAmount(any(), eq(10_000L))).willReturn(List.of(billing));

		Transaction transaction = transactionClassificationService.fromAccount(
				user, account, accountTransaction("2", "출금", null)
		);

		assertThat(transaction.getTransactionType()).isEqualTo(TransactionType.CARD_BILL);
		assertThat(transaction.getConfirmStatus()).isEqualTo(ConfirmStatus.CONFIRMED);
		assertThat(transaction.getExcludeTag()).isEqualTo(ExcludeTag.NONE);
		assertThat(transaction.getCardId()).isEqualTo(CARD_ID);
		assertThat(transaction.getSubcategoryId()).isNull();
		assertCommonAccountFields(transaction);
		assertThat(billing.isPaid()).isTrue();
		assertThat(billing.getPaidAt()).isEqualTo(LocalDateTime.of(2026, 9, 14, 10, 32, 29));
		then(cardBillingRepository).should().save(billing);
	}

	@Test
	void 이미_납부된_청구서도_매칭하되_다시_저장하지_않는다() {
		card.updateWithdrawalWeekday(1);
		CardBilling billing = CardBilling.sync(CARD_ID, LocalDate.of(2026, 9, 14), 10_000L, true,
				LocalDateTime.of(2026, 9, 14, 16, 0));
		given(cardRepository.findAllByUserIdAndManagedTrueAndWithdrawalAccountId(USER_ID, ACCOUNT_ID)).willReturn(List.of(card));
		given(cardBillingRepository.findAllByCardIdInAndTotalAmount(any(), eq(10_000L))).willReturn(List.of(billing));

		Transaction transaction = transactionClassificationService.fromAccount(
				user, account, accountTransaction("2", "출금", null)
		);

		assertThat(transaction.getTransactionType()).isEqualTo(TransactionType.CARD_BILL);
		assertThat(billing.getPaidAt()).isEqualTo(LocalDateTime.of(2026, 9, 14, 16, 0));
		then(cardBillingRepository).should(never()).save(any());
	}

	@Test
	void 출금일이_다른_청구서는_매칭하지_않는다() {
		card.updateWithdrawalWeekday(1);
		CardBilling billing = CardBilling.sync(CARD_ID, LocalDate.of(2026, 9, 7), 10_000L, false, null);
		given(cardRepository.findAllByUserIdAndManagedTrueAndWithdrawalAccountId(USER_ID, ACCOUNT_ID)).willReturn(List.of(card));
		given(cardBillingRepository.findAllByCardIdInAndTotalAmount(any(), eq(10_000L))).willReturn(List.of(billing));

		Transaction transaction = transactionClassificationService.fromAccount(
				user, account, accountTransaction("2", "출금", null)
		);

		assertThat(transaction.getTransactionType()).isEqualTo(TransactionType.WITHDRAW);
		assertThat(transaction.getConfirmStatus()).isEqualTo(ConfirmStatus.PENDING);
		assertThat(billing.isPaid()).isFalse();
		then(cardBillingRepository).should(never()).save(any());
	}

	@Test
	void 후보_청구서가_둘이면_매칭하지_않고_사용자에게_묻는다() {
		card.updateWithdrawalWeekday(1);
		Card other = Card.sync(user, "1005518816096480", "726", "1005", "신한 Deep Dream", account);
		ReflectionTestUtils.setField(other, "id", CARD_ID + 1);
		other.updateWithdrawalWeekday(1);
		given(cardRepository.findAllByUserIdAndManagedTrueAndWithdrawalAccountId(USER_ID, ACCOUNT_ID))
				.willReturn(List.of(card, other));
		given(cardBillingRepository.findAllByCardIdInAndTotalAmount(any(), eq(10_000L))).willReturn(List.of(
				CardBilling.sync(CARD_ID, LocalDate.of(2026, 9, 14), 10_000L, false, null),
				CardBilling.sync(CARD_ID + 1, LocalDate.of(2026, 9, 14), 10_000L, false, null)
		));

		Transaction transaction = transactionClassificationService.fromAccount(
				user, account, accountTransaction("2", "출금", null)
		);

		assertThat(transaction.getTransactionType()).isEqualTo(TransactionType.WITHDRAW);
		assertThat(transaction.getConfirmStatus()).isEqualTo(ConfirmStatus.PENDING);
		then(cardBillingRepository).should(never()).save(any());
	}

	@Test
	void 출금_요일이_없는_카드는_청구서를_조회하지_않는다() {
		given(cardRepository.findAllByUserIdAndManagedTrueAndWithdrawalAccountId(USER_ID, ACCOUNT_ID)).willReturn(List.of(card));

		Transaction transaction = transactionClassificationService.fromAccount(
				user, account, accountTransaction("2", "출금", null)
		);

		assertThat(transaction.getTransactionType()).isEqualTo(TransactionType.WITHDRAW);
		assertThat(transaction.getConfirmStatus()).isEqualTo(ConfirmStatus.PENDING);
		then(cardBillingRepository).shouldHaveNoInteractions();
	}

	@Test
	void 입금은_청구서를_찾지_않는다() {
		transactionClassificationService.fromAccount(user, account, accountTransaction("1", "입금", null));

		then(cardRepository).shouldHaveNoInteractions();
		then(cardBillingRepository).shouldHaveNoInteractions();
	}

	@Test
	void 연결된_본인_계좌_이체는_SELF_TRANSFER로_변환한다() {
		given(accountRepository.findByUserIdAndFinAccountNoAndManagedTrue(USER_ID, "0204667768182760"))
				.willReturn(Optional.of(account));

		Transaction transaction = transactionClassificationService.fromAccount(
				user, account, accountTransaction("2", "출금(이체)", "0204667768182760")
		);

		assertThat(transaction.getTransactionType()).isEqualTo(TransactionType.TRANSFER);
		assertThat(transaction.getConfirmStatus()).isEqualTo(ConfirmStatus.CONFIRMED);
		assertThat(transaction.getExcludeTag()).isEqualTo(ExcludeTag.SELF_TRANSFER);
	}

	@Test
	void 타인_계좌_출금_이체는_PENDING으로_변환한다() {
		given(accountRepository.findByUserIdAndFinAccountNoAndManagedTrue(USER_ID, "9999999999999999"))
				.willReturn(Optional.empty());

		Transaction transaction = transactionClassificationService.fromAccount(
				user, account, accountTransaction("2", "출금(이체)", "9999999999999999")
		);

		assertThat(transaction.getTransactionType()).isEqualTo(TransactionType.TRANSFER);
		assertThat(transaction.getConfirmStatus()).isEqualTo(ConfirmStatus.PENDING);
		assertThat(transaction.getExcludeTag()).isEqualTo(ExcludeTag.NONE);
	}

	@Test
	void 등록_가맹점_카드_결제는_AUTO로_변환한다() {
		given(merchantClassificationRepository.findByFinanceMerchantId(40_114L))
				.willReturn(Optional.of(new MerchantClassification(12L, 203)));

		Transaction transaction = transactionClassificationService.fromCard(user, card, cardTransaction("승인"));

		assertThat(transaction.getTransactionType()).isEqualTo(TransactionType.CARD);
		assertThat(transaction.getMerchantId()).isEqualTo(12L);
		assertThat(transaction.getSubcategoryId()).isEqualTo(203);
		assertThat(transaction.getConfirmStatus()).isEqualTo(ConfirmStatus.AUTO);
		assertThat(transaction.getStatus()).isEqualTo(TransactionStatus.NORMAL);
		assertThat(transaction.getMerchantNameRaw()).isEqualTo("현대오일뱅크");
	}

	@Test
	void 미등록_가맹점_카드_결제는_PENDING으로_변환한다() {
		given(merchantClassificationRepository.findByFinanceMerchantId(40_114L))
				.willReturn(Optional.empty());

		Transaction transaction = transactionClassificationService.fromCard(user, card, cardTransaction("승인"));

		assertThat(transaction.getMerchantId()).isNull();
		assertThat(transaction.getSubcategoryId()).isNull();
		assertThat(transaction.getConfirmStatus()).isEqualTo(ConfirmStatus.PENDING);
	}

	@Test
	void 카드_취소는_CANCELED로_변환한다() {
		given(merchantClassificationRepository.findByFinanceMerchantId(40_114L))
				.willReturn(Optional.of(new MerchantClassification(12L, 203)));

		Transaction transaction = transactionClassificationService.fromCard(user, card, cardTransaction("취소"));

		assertThat(transaction.getStatus()).isEqualTo(TransactionStatus.CANCELED);
	}

	@Test
	void 알_수_없는_카드_상태는_잘못된_응답으로_처리한다() {
		given(merchantClassificationRepository.findByFinanceMerchantId(40_114L))
				.willReturn(Optional.empty());

		assertThatThrownBy(() -> transactionClassificationService.fromCard(
				user, card, cardTransaction("알 수 없음")))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode()).isEqualTo(FinanceErrorCode.INVALID_RESPONSE));
	}

	private FinanceAccountTransaction accountTransaction(
			String type,
			String typeName,
			String counterAccountNo
	) {
		return new FinanceAccountTransaction(
				"61", "20260914", "103229", type, typeName, counterAccountNo,
				10_000L, 990_000L, "계좌 거래", null
		);
	}

	private FinanceCardTransaction cardTransaction(String cardStatus) {
		return new FinanceCardTransaction(
				"20", "CG-3fa85f6425e811e", "주유", 40_114L, "현대오일뱅크",
				"20260914", "094431", 1_000_000L, cardStatus, "N", "미결제"
		);
	}

	private void assertCommonAccountFields(Transaction transaction) {
		assertThat(transaction.getUser()).isEqualTo(user);
		assertThat(transaction.getAccountId()).isEqualTo(ACCOUNT_ID);
		assertThat(transaction.getSource().name()).isEqualTo("LIVE");
		assertThat(transaction.getFinTransactionUniqueNo()).isEqualTo("61");
		assertThat(transaction.getAmount()).isEqualTo(10_000L);
		assertThat(transaction.getTransactionDate()).isEqualTo(LocalDate.of(2026, 9, 14));
		assertThat(transaction.getTransactionTime()).isEqualTo(LocalTime.of(10, 32, 29));
		assertThat(transaction.getStatus()).isEqualTo(TransactionStatus.NORMAL);
	}
}
