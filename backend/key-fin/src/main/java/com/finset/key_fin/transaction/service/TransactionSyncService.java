package com.finset.key_fin.transaction.service;

import com.finset.key_fin.account.entity.Account;
import com.finset.key_fin.account.repository.AccountRepository;
import com.finset.key_fin.card.entity.Card;
import com.finset.key_fin.card.repository.CardRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.link.exception.LinkErrorCode;
import com.finset.key_fin.transaction.client.FinanceAccountTransactionClient;
import com.finset.key_fin.transaction.client.FinanceCardTransactionClient;
import com.finset.key_fin.transaction.dto.finance.response.FinanceAccountTransaction;
import com.finset.key_fin.transaction.dto.finance.response.FinanceCardTransaction;
import com.finset.key_fin.transaction.entity.ConfirmStatus;
import com.finset.key_fin.transaction.entity.ExcludeTag;
import com.finset.key_fin.transaction.entity.Transaction;
import com.finset.key_fin.transaction.entity.TransactionStatus;
import com.finset.key_fin.transaction.repository.SubcategoryQueryRepository;
import com.finset.key_fin.transaction.repository.TransactionRepository;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.Clock;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

@Service
@RequiredArgsConstructor
public class TransactionSyncService {

	private static final List<ConfirmStatus> RECLASSIFIABLE_STATUSES = List.of(
			ConfirmStatus.PENDING,
			ConfirmStatus.AUTO
	);

	private final SubcategoryQueryRepository subcategoryQueryRepository;
	private final UserRepository userRepository;
	private final AccountRepository accountRepository;
	private final CardRepository cardRepository;
	private final TransactionRepository transactionRepository;
	private final FinanceAccountTransactionClient accountTransactionClient;
	private final FinanceCardTransactionClient cardTransactionClient;
	private final TransactionClassificationService classificationService;
	private final TransactionSyncWriter syncWriter;
	private final Clock clock;

	public void sync(long userId, LocalDate startDate, LocalDate endDate) {
		validatePeriod(startDate, endDate);
		User user = requireActiveUser(userId);
		String userKey = requireFinanceUserKey(user);
		List<Account> accounts = accountRepository.findAllByUserIdAndManagedTrueOrderByIdAsc(userId);
		List<Card> cards = cardRepository.findAllByUserIdAndManagedTrueOrderByIdAsc(userId);
		List<Transaction> newTransactions = new ArrayList<>();
		List<Account> balanceUpdatedAccounts = new ArrayList<>();
		Set<String> transactionNumbers = new HashSet<>();
		Map<Long, Transaction> canceledTransactions = new LinkedHashMap<>();
		Map<Integer, Long> changedEnvelopes = new LinkedHashMap<>();
		syncAccountTransactions(
				user, userKey, accounts, startDate, endDate,
				transactionNumbers, newTransactions, balanceUpdatedAccounts);
		syncCardTransactions(
				user, userKey, cards, startDate, endDate,
				transactionNumbers, newTransactions, canceledTransactions, changedEnvelopes);
		syncWriter.save(user.getId(), balanceUpdatedAccounts, newTransactions, canceledTransactions, changedEnvelopes);
	}

	public void syncAccountTransactions(
			User user,
			Account account,
			LocalDate startDate,
			LocalDate endDate
	) {
		validatePeriod(startDate, endDate);
		validateManagedAccount(user, account);
		String userKey = requireFinanceUserKey(user);
		List<Transaction> newTransactions = new ArrayList<>();
		List<Account> balanceUpdatedAccounts = new ArrayList<>();
		syncAccountTransactions(
				user, userKey, List.of(account), startDate, endDate,
				new HashSet<>(), newTransactions, balanceUpdatedAccounts);
		syncWriter.save(user.getId(), balanceUpdatedAccounts, newTransactions, Map.of(), Map.of());
	}

	public void syncCardTransactions(
			User user,
			Card card,
			LocalDate startDate,
			LocalDate endDate
	) {
		validatePeriod(startDate, endDate);
		validateManagedCard(user, card);
		String userKey = requireFinanceUserKey(user);
		List<Transaction> newTransactions = new ArrayList<>();
		Map<Long, Transaction> canceledTransactions = new LinkedHashMap<>();
		Map<Integer, Long> changedEnvelopes = new LinkedHashMap<>();
		syncCardTransactions(
				user, userKey, List.of(card), startDate, endDate,
				new HashSet<>(), newTransactions, canceledTransactions, changedEnvelopes);
		syncWriter.save(user.getId(), List.of(), newTransactions, canceledTransactions, changedEnvelopes);
	}

	public void syncNewlyManagedAccountHistory(
			long userId,
			long accountId,
			LocalDate startDate,
			LocalDate endDate
	) {
		validatePeriod(startDate, endDate);
		User user = requireActiveUser(userId);
		String userKey = requireFinanceUserKey(user);
		Account account = requireManagedAccount(userId, accountId);
		List<Transaction> newTransactions = new ArrayList<>();
		Map<Long, Transaction> reclassifiedTransactions = new LinkedHashMap<>();
		List<Account> balanceUpdatedAccounts = new ArrayList<>();
		Map<Integer, Long> changedEnvelopes = new LinkedHashMap<>();

		syncNewlyManagedAccountTransactions(
				user, userKey, account, startDate, endDate,
				new HashSet<>(), newTransactions, reclassifiedTransactions, balanceUpdatedAccounts, changedEnvelopes);
		syncWriter.saveHistory(user.getId(), balanceUpdatedAccounts, newTransactions, reclassifiedTransactions, changedEnvelopes);
	}

	private void syncAccountTransactions(
			User user,
			String userKey,
			List<Account> accounts,
			LocalDate startDate,
			LocalDate endDate,
			Set<String> transactionNumbers,
			List<Transaction> newTransactions,
			List<Account> balanceUpdatedAccounts
	) {
		for (Account account : accounts) {
			List<FinanceAccountTransaction> financeTransactions = accountTransactionClient.findTransactions(
					userKey, account.getFinAccountNo(), startDate, endDate);
			for (FinanceAccountTransaction financeTransaction : financeTransactions) {
				if (isDuplicate(user.getId(), financeTransaction.transactionUniqueNo(), transactionNumbers)) {
					continue;
				}
				Transaction transaction = classificationService.fromAccount(user, account, financeTransaction);
				newTransactions.add(transaction);
			}
			updateBalanceFromLatestFinanceTransaction(
					account, financeTransactions, balanceUpdatedAccounts);
		}
	}

	private void syncNewlyManagedAccountTransactions(
			User user,
			String userKey,
			Account account,
			LocalDate startDate,
			LocalDate endDate,
			Set<String> transactionNumbers,
			List<Transaction> newTransactions,
			Map<Long, Transaction> reclassifiedTransactions,
			List<Account> balanceUpdatedAccounts,
			Map<Integer, Long> changedEnvelopes
	) {
		List<FinanceAccountTransaction> financeTransactions = accountTransactionClient.findTransactions(
				userKey, account.getFinAccountNo(), startDate, endDate);
		for (FinanceAccountTransaction financeTransaction : financeTransactions) {
			if (isDuplicate(user.getId(), financeTransaction.transactionUniqueNo(), transactionNumbers)) {
				continue;
			}
			Transaction transaction = classificationService.fromAccount(user, account, financeTransaction);
			reclassifyCounterpart(
					user.getId(), transaction, financeTransaction, reclassifiedTransactions, changedEnvelopes);
			newTransactions.add(transaction);
		}
		updateBalanceFromLatestFinanceTransaction(
				account, financeTransactions, balanceUpdatedAccounts);
	}

	private void syncCardTransactions(
			User user,
			String userKey,
			List<Card> cards,
			LocalDate startDate,
			LocalDate endDate,
			Set<String> transactionNumbers,
			List<Transaction> newTransactions,
			Map<Long, Transaction> canceledTransactions,
			Map<Integer, Long> changedEnvelopes
	) {
		for (Card card : cards) {
			List<FinanceCardTransaction> financeTransactions = cardTransactionClient.findTransactions(
					userKey, card.getFinCardNo(), card.getCvc(), startDate, endDate);
			for (FinanceCardTransaction financeTransaction : financeTransactions) {
				if (!transactionNumbers.add(financeTransaction.transactionUniqueNo())) {
					continue;
				}
				Optional<Transaction> stored = transactionRepository.findByUserIdAndFinTransactionUniqueNo(
						user.getId(), financeTransaction.transactionUniqueNo());
				if (stored.isPresent()) {
					cancelIfRevoked(user.getId(), stored.get(), financeTransaction, canceledTransactions, changedEnvelopes);
					continue;
				}
				newTransactions.add(classificationService.fromCard(user, card, financeTransaction));
			}
		}
	}

	/** 금융망 취소는 같은 거래번호의 cardStatus 만 바뀌므로 이미 수집한 승인 건을 취소로 옮긴다. */
	private void cancelIfRevoked(
			long userId,
			Transaction transaction,
			FinanceCardTransaction financeTransaction,
			Map<Long, Transaction> canceledTransactions,
			Map<Integer, Long> changedEnvelopes
	) {
		if (transaction.getStatus() != TransactionStatus.NORMAL
				|| !classificationService.isCardCanceled(financeTransaction)) {
			return;
		}
		transaction.cancel();
		canceledTransactions.put(transaction.getId(), transaction);
		if (transaction.getSubcategoryId() != null) {
			subcategoryQueryRepository.findEnvelopeId(transaction.getSubcategoryId())
					.ifPresent(envelopeId -> changedEnvelopes.merge(envelopeId, transaction.getAmount(), Long::sum));
		}
	}

	private void updateBalanceFromLatestFinanceTransaction(
			Account account,
			List<FinanceAccountTransaction> financeTransactions,
			List<Account> balanceUpdatedAccounts
	) {
		if (financeTransactions.isEmpty()) {
			return;
		}
		FinanceAccountTransaction latestTransaction = financeTransactions.getLast();
		account.updateBalanceSnapshot(
				account.getBankName(),
				latestTransaction.transactionAfterBalance(),
				LocalDateTime.now(clock)
		);
		balanceUpdatedAccounts.add(account);
	}

	private boolean isDuplicate(long userId, String transactionNumber, Set<String> transactionNumbers) {
		if (!transactionNumbers.add(transactionNumber)) {
			return true;
		}
		return transactionRepository.existsByUserIdAndFinTransactionUniqueNo(userId, transactionNumber);
	}

	private void reclassifyCounterpart(
			long userId,
			Transaction transaction,
			FinanceAccountTransaction financeTransaction,
			Map<Long, Transaction> reclassifiedTransactions,
			Map<Integer, Long> changedEnvelopes
	) {
		if (transaction.getExcludeTag() != ExcludeTag.SELF_TRANSFER) {
			return;
		}
		accountRepository.findByUserIdAndFinAccountNoAndManagedTrue(
					userId, financeTransaction.transactionAccountNo())
				.flatMap(counterpartAccount -> transactionRepository
						.findFirstByUserIdAndAccountIdAndTransactionDateAndTransactionTimeAndAmountAndStatusAndExcludeTagNotAndConfirmStatusInOrderByIdDesc(
								userId,
								counterpartAccount.getId(),
								transaction.getTransactionDate(),
								transaction.getTransactionTime(),
								transaction.getAmount(),
								TransactionStatus.NORMAL,
								ExcludeTag.SELF_TRANSFER,
								RECLASSIFIABLE_STATUSES
						))
				.ifPresent(counterpartTransaction -> {
					Integer before = counterpartTransaction.getSubcategoryId();
					counterpartTransaction.markAsSelfTransfer();
					reclassifiedTransactions.put(counterpartTransaction.getId(), counterpartTransaction);
					if (before != null) {
						subcategoryQueryRepository.findEnvelopeId(before)
								.ifPresent(envelopeId -> changedEnvelopes.putIfAbsent(envelopeId, null));
					}
				});
	}

	private User requireActiveUser(long userId) {
		return userRepository.findByIdAndDeletedAtIsNull(userId)
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_NOT_FOUND));
	}

	private Account requireManagedAccount(long userId, long accountId) {
		Account account = accountRepository.findByIdAndUserId(accountId, userId)
				.orElseThrow(() -> new BusinessException(LinkErrorCode.ACCOUNT_NOT_FOUND));
		if (!account.isManaged()) {
			throw new BusinessException(LinkErrorCode.ACCOUNT_NOT_FOUND);
		}
		return account;
	}

	private void validateManagedAccount(User user, Account account) {
		if (user == null || account == null || !account.isManaged()
				|| !user.getId().equals(account.getUser().getId())) {
			throw new BusinessException(LinkErrorCode.ACCOUNT_NOT_FOUND);
		}
	}

	private void validateManagedCard(User user, Card card) {
		if (user == null || card == null || !card.isManaged()
				|| !user.getId().equals(card.getUser().getId())) {
			throw new BusinessException(LinkErrorCode.CARD_NOT_FOUND);
		}
	}

	private String requireFinanceUserKey(User user) {
		if (!user.isFinanceConnected()) {
			throw new BusinessException(LinkErrorCode.FINANCE_NOT_CONNECTED);
		}
		return user.getFinUserKey();
	}

	private void validatePeriod(LocalDate startDate, LocalDate endDate) {
		if (startDate == null || endDate == null || startDate.isAfter(endDate)) {
			throw new IllegalArgumentException("거래 조회 기간이 올바르지 않습니다.");
		}
	}
}
