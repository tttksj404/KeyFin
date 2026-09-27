package com.finset.key_fin.transaction.service;

import com.finset.key_fin.account.entity.Account;
import com.finset.key_fin.account.repository.AccountRepository;
import com.finset.key_fin.card.entity.Card;
import com.finset.key_fin.card.repository.CardRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.finance.exception.FinanceErrorCode;
import com.finset.key_fin.payment.entity.CardBilling;
import com.finset.key_fin.payment.repository.CardBillingRepository;
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
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.DateTimeException;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class TransactionClassificationService {

	private static final DateTimeFormatter DATE_FORMAT = DateTimeFormatter.BASIC_ISO_DATE;
	private static final DateTimeFormatter TIME_FORMAT = DateTimeFormatter.ofPattern("HHmmss");
	private static final String CARD_APPROVED = "승인";
	private static final String CARD_CANCELED = "취소";

	private final AccountRepository accountRepository;
	private final MerchantClassificationRepository merchantClassificationRepository;
	private final CardRepository cardRepository;
	private final CardBillingRepository cardBillingRepository;

	public Transaction fromAccount(
			User user,
			Account account,
			FinanceAccountTransaction financeTransaction
	) {
		boolean transfer = isTransfer(financeTransaction.transactionTypeName());
		boolean ownAccountTransfer = transfer
				&& hasText(financeTransaction.transactionAccountNo())
				&& accountRepository.findByUserIdAndFinAccountNoAndManagedTrue(
						user.getId(), financeTransaction.transactionAccountNo()).isPresent();

		TransactionType transactionType = accountTransactionType(
				financeTransaction.transactionTypeName(), ownAccountTransfer
		);
		if (!ownAccountTransfer && transactionType != TransactionType.DEPOSIT) {
			CardBilling billing = matchCardBilling(user.getId(), account.getId(),
					financeTransaction.transactionBalance(), parseDate(financeTransaction.transactionDate()));
			if (billing != null) {
				markPaid(billing, financeTransaction);
				return Transaction.collectCardBill(
						user,
						account.getId(),
						billing.getCardId(),
						financeTransaction.transactionUniqueNo(),
						firstNonBlank(financeTransaction.transactionSummary(), financeTransaction.transactionMemo()),
						financeTransaction.transactionBalance(),
						parseDate(financeTransaction.transactionDate()),
						parseTime(financeTransaction.transactionTime())
				);
			}
		}
		ConfirmStatus confirmStatus;
		ExcludeTag excludeTag;

		if (ownAccountTransfer) {
			confirmStatus = ConfirmStatus.CONFIRMED;
			excludeTag = ExcludeTag.SELF_TRANSFER;
		} else if (transactionType == TransactionType.DEPOSIT) {
			confirmStatus = ConfirmStatus.AUTO;
			excludeTag = ExcludeTag.NONE;
		} else {
			confirmStatus = ConfirmStatus.PENDING;
			excludeTag = ExcludeTag.NONE;
		}

		return Transaction.collectAccount(
				user,
				account.getId(),
				financeTransaction.transactionUniqueNo(),
				transactionType,
				firstNonBlank(financeTransaction.transactionSummary(), financeTransaction.transactionMemo()),
				financeTransaction.transactionBalance(),
				parseDate(financeTransaction.transactionDate()),
				parseTime(financeTransaction.transactionTime()),
				confirmStatus,
				excludeTag
		);
	}

	public Transaction fromCard(
			User user,
			Card card,
			FinanceCardTransaction financeTransaction
	) {
		MerchantClassification classification = findMerchantClassification(financeTransaction.merchantId());
		Long merchantId = null;
		Integer subcategoryId = null;
		ConfirmStatus confirmStatus = ConfirmStatus.PENDING;

		if (classification != null) {
			merchantId = classification.merchantId();
			subcategoryId = classification.subcategoryId();
			confirmStatus = ConfirmStatus.AUTO;
		}

		return Transaction.collectCard(
				user,
				card.getId(),
				financeTransaction.transactionUniqueNo(),
				merchantId,
				financeTransaction.merchantName(),
				financeTransaction.transactionBalance(),
				parseDate(financeTransaction.transactionDate()),
				parseTime(financeTransaction.transactionTime()),
				subcategoryId,
				confirmStatus,
				cardStatus(financeTransaction.cardStatus())
		);
	}

	/** 17:00 동기화보다 먼저 납부를 반영한다. 금융망 상태가 다르면 동기화가 다시 덮어쓴다. */
	private void markPaid(CardBilling billing, FinanceAccountTransaction financeTransaction) {
		if (billing.isPaid()) {
			return;
		}
		billing.syncFrom(billing.getTotalAmount(), true,
				LocalDateTime.of(parseDate(financeTransaction.transactionDate()), parseTime(financeTransaction.transactionTime())));
		cardBillingRepository.save(billing);
	}

	/** 출금 계좌·금액·출금일이 맞는 청구서가 정확히 하나일 때만 카드대금으로 본다. 둘 이상이면 사용자에게 묻는다. */
	private CardBilling matchCardBilling(long userId, long accountId, long amount, LocalDate date) {
		Map<Long, Card> cards = cardRepository.findAllByUserIdAndManagedTrueAndWithdrawalAccountId(userId, accountId).stream()
				.filter(card -> card.getWithdrawalWeekday() != null)
				.collect(Collectors.toMap(Card::getId, Function.identity()));
		if (cards.isEmpty()) {
			return null;
		}
		List<CardBilling> matched = cardBillingRepository.findAllByCardIdInAndTotalAmount(cards.keySet(), amount).stream()
				.filter(billing -> billing.withdrawalDate(cards.get(billing.getCardId()).getWithdrawalWeekday()).equals(date))
				.toList();
		return matched.size() == 1 ? matched.get(0) : null;
	}

	private MerchantClassification findMerchantClassification(Long financeMerchantId) {
		if (financeMerchantId == null) {
			return null;
		}
		return merchantClassificationRepository
				.findByFinanceMerchantId(financeMerchantId)
				.orElse(null);
	}

	private TransactionType accountTransactionType(String transactionTypeName, boolean ownAccountTransfer) {
		if (!hasText(transactionTypeName)) {
			throw invalidResponse();
		}
		if (ownAccountTransfer || transactionTypeName.contains("출금(이체)")) {
			return TransactionType.TRANSFER;
		}
		if (transactionTypeName.startsWith("입금")) {
			return TransactionType.DEPOSIT;
		}
		if (transactionTypeName.startsWith("출금")) {
			return TransactionType.WITHDRAW;
		}
		throw invalidResponse();
	}

	public boolean isCardCanceled(FinanceCardTransaction financeTransaction) {
		return cardStatus(financeTransaction.cardStatus()) == TransactionStatus.CANCELED;
	}

	private TransactionStatus cardStatus(String status) {
		if (CARD_APPROVED.equals(status)) {
			return TransactionStatus.NORMAL;
		}
		if (CARD_CANCELED.equals(status)) {
			return TransactionStatus.CANCELED;
		}
		throw invalidResponse();
	}

	private boolean isTransfer(String transactionTypeName) {
		return "입금(이체)".equals(transactionTypeName) || "출금(이체)".equals(transactionTypeName);
	}

	private LocalDate parseDate(String value) {
		try {
			return LocalDate.parse(value, DATE_FORMAT);
		} catch (DateTimeException | NullPointerException exception) {
			throw invalidResponse(exception);
		}
	}

	private LocalTime parseTime(String value) {
		try {
			return LocalTime.parse(value, TIME_FORMAT);
		} catch (DateTimeException | NullPointerException exception) {
			throw invalidResponse(exception);
		}
	}

	private String firstNonBlank(String first, String second) {
		if (hasText(first)) {
			return first;
		}
		return second;
	}

	private boolean hasText(String value) {
		return value != null && !value.isBlank();
	}

	private BusinessException invalidResponse() {
		return new BusinessException(FinanceErrorCode.INVALID_RESPONSE);
	}

	private BusinessException invalidResponse(Throwable cause) {
		return new BusinessException(FinanceErrorCode.INVALID_RESPONSE, cause);
	}
}
