package com.finset.key_fin.coaching.service;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.LocalDate;
import java.time.LocalTime;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import com.finset.key_fin.coaching.dto.FdtTransaction;
import com.finset.key_fin.transaction.entity.ConfirmStatus;
import com.finset.key_fin.transaction.entity.ExcludeTag;
import com.finset.key_fin.transaction.entity.Transaction;
import com.finset.key_fin.transaction.entity.TransactionStatus;
import com.finset.key_fin.transaction.entity.TransactionType;
import com.finset.key_fin.user.entity.User;

class FdtTransactionMapperTest {

	private final FdtTransactionMapper mapper = new FdtTransactionMapper(new FdtCategoryMapper());

	@Test
	void 카드_거래를_필수_항목으로_변환한다() {
		Transaction transaction = cardTransaction(12_000L, 31L, "메가MGC커피 선릉역점", 102);

		FdtTransaction result = mapper.map(transaction);

		assertThat(result.transactionType()).isEqualTo("CARD");
		assertThat(result.category()).isEqualTo("식비");
		assertThat(result.subcategory()).isEqualTo("카페");
		assertThat(result.merchantId()).isEqualTo("31");
		assertThat(result.merchant()).isEqualTo("메가MGC커피 선릉역점");
		assertThat(result.amountKrw()).isEqualTo(12_000L);
		assertThat(result.cardId()).isEqualTo("7");
		assertThat(result.accountId()).isEmpty();
		assertThat(result.transactionDate()).isEqualTo("2026-09-10");
		assertThat(result.transactionTime()).isEqualTo("12:30:00");
		assertThat(result.status()).isEqualTo("NORMAL");
	}

	@Test
	void 미매핑_카드_거래는_가맹점명을_식별자에_붙인다() {
		Transaction transaction = cardTransaction(8_000L, null, "이름없는김밥", null);

		FdtTransaction result = mapper.map(transaction);

		assertThat(result.merchantId()).isEqualTo("raw:이름없는김밥");
		assertThat(result.category()).isEmpty();
		assertThat(result.subcategory()).isEmpty();
	}

	@Test
	void 계좌_거래의_가맹점_식별자는_빈_문자열이다() {
		Transaction transaction = accountTransaction(TransactionType.WITHDRAW, ExcludeTag.NONE);

		FdtTransaction result = mapper.map(transaction);

		assertThat(result.merchantId()).isEmpty();
		assertThat(result.accountId()).isEqualTo("1");
		assertThat(result.cardId()).isEmpty();
	}

	@Test
	void 본인_계좌_이동은_원장에서_제외한다() {
		Transaction selfTransfer = accountTransaction(TransactionType.TRANSFER, ExcludeTag.SELF_TRANSFER);
		Transaction outgoing = accountTransaction(TransactionType.TRANSFER, ExcludeTag.NONE);

		List<FdtTransaction> result = mapper.map(List.of(selfTransfer, outgoing));

		assertThat(result).hasSize(1);
		assertThat(result.get(0).transactionType()).isEqualTo("TRANSFER_OUT");
	}

	@Test
	void 남에게_나가는_송금은_TRANSFER_OUT으로_보낸다() {
		Transaction transaction = accountTransaction(TransactionType.TRANSFER, ExcludeTag.NONE);

		FdtTransaction result = mapper.map(transaction);

		assertThat(result.transactionType()).isEqualTo("TRANSFER_OUT");
	}

	@Test
	void RESTORE는_DEPOSIT과_NONE으로_바꾼다() {
		Transaction transaction = accountTransaction(TransactionType.DEPOSIT, ExcludeTag.RESTORE);

		FdtTransaction result = mapper.map(transaction);

		assertThat(result.transactionType()).isEqualTo("DEPOSIT");
		assertThat(result.excludeTag()).isEqualTo("NONE");
	}

	@Test
	void DUTCH는_태그를_유지하고_실제_결제액을_보낸다() {
		Transaction transaction = cardTransaction(100_000L, 31L, "회식", 101);
		ReflectionTestUtils.setField(transaction, "excludeTag", ExcludeTag.DUTCH);
		ReflectionTestUtils.setField(transaction, "adjustedAmount", 40_000L);

		FdtTransaction result = mapper.map(transaction);

		assertThat(result.excludeTag()).isEqualTo("DUTCH");
		assertThat(result.amountKrw()).isEqualTo(100_000L);
	}

	@Test
	void BUDGET_EXCLUDED는_유형을_바꾸지_않고_태그_그대로_보낸다() {
		Transaction transaction = accountTransaction(TransactionType.WITHDRAW, ExcludeTag.BUDGET_EXCLUDED);

		FdtTransaction result = mapper.map(transaction);

		assertThat(result.transactionType()).isEqualTo("WITHDRAW");
		assertThat(result.excludeTag()).isEqualTo("BUDGET_EXCLUDED");
	}

	/** 엔진이 받지 않는 값을 보내면 원장 적재가 통째로 거부된다. 태그가 늘어나면 여기서 걸린다. */
	@Test
	void 모든_태그가_엔진_enum_안의_값으로_나간다() {
		List<String> engineEnum = List.of("NONE", "INTERNAL_TRANSFER", "SELF_TRANSFER", "DUTCH",
				"EMERGENCY", "CARRYOVER", "BUDGET_EXCLUDED");

		for (ExcludeTag tag : ExcludeTag.values()) {
			if (tag == ExcludeTag.CARRYOVER || tag == ExcludeTag.SELF_TRANSFER) {
				continue; // 원장에서 제외되어 전송되지 않는다
			}
			Transaction transaction = accountTransaction(
					tag == ExcludeTag.RESTORE ? TransactionType.DEPOSIT : TransactionType.WITHDRAW, tag);
			if (tag == ExcludeTag.DUTCH) {
				ReflectionTestUtils.setField(transaction, "adjustedAmount", 10_000L);
			}

			assertThat(mapper.map(transaction).excludeTag())
					.as("태그 %s", tag)
					.isIn(engineEnum);
		}
	}

	@Test
	void CARRYOVER는_원장에서_제외한다() {
		Transaction carryover = accountTransaction(TransactionType.DEPOSIT, ExcludeTag.CARRYOVER);
		Transaction normal = accountTransaction(TransactionType.WITHDRAW, ExcludeTag.NONE);

		List<FdtTransaction> result = mapper.map(List.of(carryover, normal));

		assertThat(result).hasSize(1);
		assertThat(result.get(0).transactionType()).isEqualTo("WITHDRAW");
	}

	@Test
	void 카드대금_출금은_CARD_SETTLEMENT로_계좌만_실어_보낸다() {
		Transaction transaction = Transaction.collectCardBill(
				user(), 1L, 7L, "202609210003", "카드대금 출금", 1_300L,
				LocalDate.of(2026, 9, 21), LocalTime.of(16, 0, 4)
		);
		ReflectionTestUtils.setField(transaction, "id", 300L);

		FdtTransaction result = mapper.map(transaction);

		assertThat(result.transactionType()).isEqualTo("CARD_SETTLEMENT");
		assertThat(result.accountId()).isEqualTo("1");
		assertThat(result.cardId()).isEmpty();
		assertThat(result.merchantId()).isEmpty();
		assertThat(result.confirmStatus()).isEqualTo("CONFIRMED");
		assertThat(result.excludeTag()).isEqualTo("NONE");
	}

	@Test
	void 취소된_거래도_상태를_유지해_보낸다() {
		Transaction transaction = cardTransaction(5_000L, 31L, "취소건", 102);
		ReflectionTestUtils.setField(transaction, "status", TransactionStatus.CANCELED);

		FdtTransaction result = mapper.map(transaction);

		assertThat(result.status()).isEqualTo("CANCELED");
	}

	private Transaction cardTransaction(long amount, Long merchantId, String merchantName, Integer subcategoryId) {
		Transaction transaction = Transaction.collectCard(
				user(), 7L, "202609100001", merchantId, merchantName, amount,
				LocalDate.of(2026, 9, 10), LocalTime.of(12, 30), subcategoryId,
				subcategoryId == null ? ConfirmStatus.PENDING : ConfirmStatus.AUTO, TransactionStatus.NORMAL
		);
		ReflectionTestUtils.setField(transaction, "id", 100L);
		return transaction;
	}

	private Transaction accountTransaction(TransactionType type, ExcludeTag excludeTag) {
		Transaction transaction = Transaction.collectAccount(
				user(), 1L, "202609100002", type, "계좌 거래", 750_000L,
				LocalDate.of(2026, 9, 5), LocalTime.of(9, 0), ConfirmStatus.CONFIRMED, excludeTag
		);
		ReflectionTestUtils.setField(transaction, "id", 200L);
		return transaction;
	}

	private User user() {
		User user = User.create("keyfin-tester@example.com", "password", "정재원");
		ReflectionTestUtils.setField(user, "id", 1L);
		return user;
	}
}
