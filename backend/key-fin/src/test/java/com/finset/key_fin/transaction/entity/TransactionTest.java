package com.finset.key_fin.transaction.entity;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.transaction.exception.TransactionErrorCode;
import com.finset.key_fin.user.entity.User;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalDate;
import java.time.LocalTime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class TransactionTest {

	@Test
	void appliesDatabaseDefaults() {
		Transaction transaction = new Transaction();

		assertThat(transaction.getConfirmStatus()).isEqualTo(ConfirmStatus.PENDING);
		assertThat(transaction.getExcludeTag()).isEqualTo(ExcludeTag.NONE);
		assertThat(transaction.getStatus()).isEqualTo(TransactionStatus.NORMAL);
	}

	@Test
	void supportsRestoreExcludeTag() {
		assertThat(ExcludeTag.valueOf("RESTORE")).isEqualTo(ExcludeTag.RESTORE);
	}

	@Test
	void 세분류를_확정하면_제외_정보를_초기화한다() {
		Transaction transaction = cardTransaction(40_000L);
		ReflectionTestUtils.setField(transaction, "excludeTag", ExcludeTag.DUTCH);
		ReflectionTestUtils.setField(transaction, "adjustedAmount", 20_000L);

		transaction.confirmSubcategory(102);

		assertThat(transaction.getSubcategoryId()).isEqualTo(102);
		assertThat(transaction.getExcludeTag()).isEqualTo(ExcludeTag.NONE);
		assertThat(transaction.getAdjustedAmount()).isNull();
		assertThat(transaction.getConfirmStatus()).isEqualTo(ConfirmStatus.CONFIRMED);
	}

	@Test
	void 더치페이는_실제_부담액으로_확정한다() {
		Transaction transaction = cardTransaction(40_000L);

		transaction.confirmExclusion(ExcludeTag.DUTCH, 20_000L);

		assertThat(transaction.getSubcategoryId()).isNull();
		assertThat(transaction.getExcludeTag()).isEqualTo(ExcludeTag.DUTCH);
		assertThat(transaction.getAdjustedAmount()).isEqualTo(20_000L);
		assertThat(transaction.getConfirmStatus()).isEqualTo(ConfirmStatus.CONFIRMED);
	}

	@Test
	void 더치페이_부담액이_원금보다_크면_거절한다() {
		Transaction transaction = cardTransaction(40_000L);

		assertThatThrownBy(() -> transaction.confirmExclusion(ExcludeTag.DUTCH, 40_001L))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(TransactionErrorCode.INVALID_ADJUSTED_AMOUNT));
	}

	@Test
	void 입금_거래는_분류할_수_없다() {
		Transaction transaction = cardTransaction(40_000L);
		ReflectionTestUtils.setField(transaction, "transactionType", TransactionType.DEPOSIT);

		assertThatThrownBy(() -> transaction.confirmSubcategory(102))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(TransactionErrorCode.CLASSIFICATION_NOT_ALLOWED));
	}

	@Test
	void 환급_입금은_세분류와_RESTORE로_확정한다() {
		Transaction transaction = cardTransaction(20_000L);
		ReflectionTestUtils.setField(transaction, "transactionType", TransactionType.DEPOSIT);

		transaction.confirmRestore(301);

		assertThat(transaction.getSubcategoryId()).isEqualTo(301);
		assertThat(transaction.getExcludeTag()).isEqualTo(ExcludeTag.RESTORE);
		assertThat(transaction.getAdjustedAmount()).isNull();
		assertThat(transaction.getConfirmStatus()).isEqualTo(ConfirmStatus.CONFIRMED);
	}

	@Test
	void 카드대금_출금은_다시_분류할_수_없다() {
		Transaction transaction = Transaction.collectCardBill(
				User.create("qwer@qwer.com", "password", "김예린"), 1L, 7L, "202609210003", "카드대금 출금", 1_300L,
				LocalDate.of(2026, 9, 21), LocalTime.of(16, 0, 4)
		);

		assertThat(transaction.getTransactionType()).isEqualTo(TransactionType.CARD_BILL);
		assertThat(transaction.getConfirmStatus()).isEqualTo(ConfirmStatus.CONFIRMED);
		assertThat(transaction.getAccountId()).isEqualTo(1L);
		assertThat(transaction.getCardId()).isEqualTo(7L);
		assertThatThrownBy(() -> transaction.confirmSubcategory(201))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(TransactionErrorCode.CLASSIFICATION_NOT_ALLOWED));
		assertThatThrownBy(() -> transaction.confirmExclusion(ExcludeTag.SELF_TRANSFER, null))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(TransactionErrorCode.CLASSIFICATION_NOT_ALLOWED));
	}

	@Test
	void 출금_거래는_RESTORE로_확정할_수_없다() {
		Transaction transaction = cardTransaction(20_000L);

		assertThatThrownBy(() -> transaction.confirmRestore(301))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(TransactionErrorCode.CLASSIFICATION_NOT_ALLOWED));
	}

	@Test
	void 계좌_거래를_본인_계좌_이체로_변경한다() {
		Transaction transaction = accountTransaction(ConfirmStatus.PENDING);

		transaction.markAsSelfTransfer();

		assertThat(transaction.getTransactionType()).isEqualTo(TransactionType.TRANSFER);
		assertThat(transaction.getSubcategoryId()).isNull();
		assertThat(transaction.getExcludeTag()).isEqualTo(ExcludeTag.SELF_TRANSFER);
		assertThat(transaction.getAdjustedAmount()).isNull();
		assertThat(transaction.getConfirmStatus()).isEqualTo(ConfirmStatus.CONFIRMED);
	}

	@Test
	void 사용자가_확정한_거래는_본인_계좌_이체로_자동_변경하지_않는다() {
		Transaction transaction = accountTransaction(ConfirmStatus.CONFIRMED);

		assertThatThrownBy(transaction::markAsSelfTransfer)
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(TransactionErrorCode.CLASSIFICATION_NOT_ALLOWED));
	}

	@Test
	void 예산_제외_거래로_확정한다() {
		Transaction transaction = cardTransaction(40_000L);

		transaction.confirmExclusion(ExcludeTag.BUDGET_EXCLUDED, null);

		assertThat(transaction.getSubcategoryId()).isNull();
		assertThat(transaction.getExcludeTag()).isEqualTo(ExcludeTag.BUDGET_EXCLUDED);
		assertThat(transaction.getAdjustedAmount()).isNull();
		assertThat(transaction.getConfirmStatus()).isEqualTo(ConfirmStatus.CONFIRMED);
	}

	@Test
	void 예산_제외_거래에_부담액을_함께_보내면_거절한다() {
		Transaction transaction = cardTransaction(40_000L);

		assertThatThrownBy(() -> transaction.confirmExclusion(ExcludeTag.BUDGET_EXCLUDED, 20_000L))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(TransactionErrorCode.INVALID_CLASSIFICATION));
	}

	@Test
	void 사용자가_고를_수_없는_제외_태그는_거절한다() {
		Transaction transaction = cardTransaction(40_000L);

		assertThatThrownBy(() -> transaction.confirmExclusion(ExcludeTag.CARRYOVER, null))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(TransactionErrorCode.INVALID_CLASSIFICATION));
	}

	@Test
	void 비상금_거래로_확정한다() {
		Transaction transaction = cardTransaction(40_000L);

		transaction.confirmExclusion(ExcludeTag.EMERGENCY, null);

		assertThat(transaction.getSubcategoryId()).isNull();
		assertThat(transaction.getExcludeTag()).isEqualTo(ExcludeTag.EMERGENCY);
		assertThat(transaction.getAdjustedAmount()).isNull();
		assertThat(transaction.getConfirmStatus()).isEqualTo(ConfirmStatus.CONFIRMED);
	}

	@Test
	void 이미_확정된_거래는_미확정_일괄_분류_대상이_아니다() {
		Transaction transaction = cardTransaction(40_000L);
		ReflectionTestUtils.setField(transaction, "confirmStatus", ConfirmStatus.CONFIRMED);

		assertThatThrownBy(transaction::validatePendingClassificationTarget)
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(TransactionErrorCode.CLASSIFICATION_NOT_ALLOWED));
	}

	@Test
	void 거래_메모의_앞뒤_공백을_제거해_저장한다() {
		Transaction transaction = cardTransaction(40_000L);

		transaction.updateMemo("  회식 — 회사에서 정산 예정  ");

		assertThat(transaction.getMemo()).isEqualTo("회식 — 회사에서 정산 예정");
	}

	@Test
	void 빈_거래_메모는_기존_메모를_삭제한다() {
		Transaction transaction = cardTransaction(40_000L);
		transaction.updateMemo("기존 메모");

		transaction.updateMemo("   ");

		assertThat(transaction.getMemo()).isNull();
	}

	private Transaction cardTransaction(long amount) {
		Transaction transaction = new Transaction();
		ReflectionTestUtils.setField(transaction, "transactionType", TransactionType.CARD);
		ReflectionTestUtils.setField(transaction, "amount", amount);
		return transaction;
	}

	private Transaction accountTransaction(ConfirmStatus confirmStatus) {
		return Transaction.collectAccount(
				User.create("qwer@qwer.com", "password", "김예린"),
				1L,
				"101",
				TransactionType.WITHDRAW,
				"계좌 거래",
				10_000L,
				LocalDate.of(2026, 9, 15),
				LocalTime.of(10, 30),
				confirmStatus,
				ExcludeTag.NONE
		);
	}
}
