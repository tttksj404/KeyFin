package com.finset.key_fin.coaching.service;

import java.time.format.DateTimeFormatter;
import java.util.List;

import org.springframework.stereotype.Component;

import com.finset.key_fin.coaching.dto.FdtTransaction;
import com.finset.key_fin.transaction.entity.ExcludeTag;
import com.finset.key_fin.transaction.entity.Transaction;
import com.finset.key_fin.transaction.entity.TransactionType;

import lombok.RequiredArgsConstructor;

/** 우리 거래를 FDT 원장 형식으로 바꾼다. */
@Component
@RequiredArgsConstructor
public class FdtTransactionMapper {

	private static final DateTimeFormatter TIME = DateTimeFormatter.ofPattern("HH:mm:ss");
	private static final String UNMAPPED_MERCHANT_PREFIX = "raw:";

	private final FdtCategoryMapper categoryMapper;

	/**
	 * CARRYOVER 는 시딩 이월 마커라 원장에서 뺀다.
	 * SELF_TRANSFER 는 엔진이 to_account_id 로 상대 계좌를 요구하는데 우리 원장은 방향·상대 계좌를 갖지 않아 뺀다.
	 * 과거 이동은 스냅샷 잔액에 이미 반영돼 있어 총현금·지출 예측에는 영향이 없다.
	 */
	public List<FdtTransaction> map(List<Transaction> transactions) {
		return transactions.stream()
				.filter(transaction -> transaction.getExcludeTag() != ExcludeTag.CARRYOVER
						&& transaction.getExcludeTag() != ExcludeTag.SELF_TRANSFER)
				.map(this::map)
				.toList();
	}

	public FdtTransaction map(Transaction transaction) {
		FdtCategoryMapper.Entry category = categoryMapper.of(transaction.getSubcategoryId());
		return new FdtTransaction(
				String.valueOf(transaction.getUser().getId()),
				String.valueOf(transaction.getId()),
				transaction.getSource().name(),
				transactionType(transaction),
				transaction.getTransactionDate().toString(),
				transaction.getTransactionTime().format(TIME),
				category.category(),
				category.subcategory(),
				nullToEmpty(transaction.getMerchantNameRaw()),
				merchantId(transaction),
				transaction.getAmount(),
				idToString(transaction.getAccountId()),
				cardId(transaction),
				transaction.getConfirmStatus().name(),
				transaction.getStatus().name(),
				excludeTag(transaction)
		);
	}

	/**
	 * RESTORE 는 봉투를 되돌리는 입금이라 FDT enum 에 없다. DEPOSIT 으로 보낸다.
	 * 본인 계좌 이동은 전송에서 빠지므로 남는 TRANSFER 는 전부 남에게 나가는 송금(TRANSFER_OUT)이다.
	 * 카드대금 출금은 CARD_SETTLEMENT 로, 계좌 현금만 줄이고 지출 분포에는 넣지 않는다.
	 */
	private String transactionType(Transaction transaction) {
		if (transaction.getExcludeTag() == ExcludeTag.RESTORE) {
			return TransactionType.DEPOSIT.name();
		}
		if (transaction.getTransactionType() == TransactionType.CARD_BILL) {
			return "CARD_SETTLEMENT";
		}
		if (transaction.getTransactionType() != TransactionType.TRANSFER) {
			return transaction.getTransactionType().name();
		}
		return "TRANSFER_OUT";
	}

	/**
	 * 엔진 enum 은 NONE·INTERNAL_TRANSFER·SELF_TRANSFER·DUTCH·EMERGENCY·CARRYOVER·BUDGET_EXCLUDED 일곱 종이다.
	 * 여기 없는 값을 보내면 원장 적재가 통째로 거부된다. BUDGET_EXCLUDED 는 엔진이 지출로 세되 봉투 집계만 뺀다.
	 */
	private String excludeTag(Transaction transaction) {
		return transaction.getExcludeTag() == ExcludeTag.RESTORE
				? ExcludeTag.NONE.name()
				: transaction.getExcludeTag().name();
	}

	/**
	 * 엔진이 이 값을 반복 지출 탐지의 묶음 키로 쓴다. 미매핑 가맹점에 같은 값을 주면
	 * 서로 다른 가게가 한 덩어리로 묶여 없는 정기 결제가 잡히므로 가맹점명을 붙인다.
	 */
	private String merchantId(Transaction transaction) {
		if (transaction.getCardId() == null || transaction.getTransactionType() == TransactionType.CARD_BILL) {
			return "";
		}
		if (transaction.getMerchantId() != null) {
			return String.valueOf(transaction.getMerchantId());
		}
		return UNMAPPED_MERCHANT_PREFIX + nullToEmpty(transaction.getMerchantNameRaw());
	}

	/** 엔진은 card_id 가 붙은 흐름을 지출로만 받는다. 정산 행은 계좌만 실어 현금 경로로 보낸다. */
	private static String cardId(Transaction transaction) {
		return transaction.getTransactionType() == TransactionType.CARD_BILL ? "" : idToString(transaction.getCardId());
	}

	private static String idToString(Long id) {
		return id == null ? "" : String.valueOf(id);
	}

	private static String nullToEmpty(String value) {
		return value == null ? "" : value;
	}
}
