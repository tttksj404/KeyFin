package com.finset.key_fin.coaching.service;

import java.time.Clock;
import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.finset.key_fin.account.entity.Account;
import com.finset.key_fin.account.repository.AccountRepository;
import com.finset.key_fin.budget.entity.Budget;
import com.finset.key_fin.budget.repository.BudgetRepository;
import com.finset.key_fin.budget.service.BudgetPeriod;
import com.finset.key_fin.budget.service.EnvelopeBalanceService;
import com.finset.key_fin.budget.service.EnvelopeBalanceService.EnvelopeBalance;
import com.finset.key_fin.card.entity.Card;
import com.finset.key_fin.card.repository.CardRepository;
import com.finset.key_fin.coaching.dto.FdtBootstrap;
import com.finset.key_fin.coaching.dto.FdtSnapshot;
import com.finset.key_fin.payment.entity.CardBilling;
import com.finset.key_fin.payment.entity.FixedExpense;
import com.finset.key_fin.payment.repository.CardBillingRepository;
import com.finset.key_fin.payment.repository.FixedExpenseRepository;
import com.finset.key_fin.transaction.repository.TransactionRepository;
import com.finset.key_fin.user.entity.UserSettings;
import com.finset.key_fin.user.repository.UserSettingsRepository;

import lombok.RequiredArgsConstructor;

/** 한 사용자의 원장과 현황을 모아 FDT Bootstrap 하나로 만든다. */
@Service
@RequiredArgsConstructor
public class FdtBootstrapService {

	private static final int DEFAULT_ANCHOR_DAY = 1;

	private final TransactionRepository transactionRepository;
	private final AccountRepository accountRepository;
	private final CardRepository cardRepository;
	private final CardBillingRepository cardBillingRepository;
	private final FixedExpenseRepository fixedExpenseRepository;
	private final BudgetRepository budgetRepository;
	private final UserSettingsRepository userSettingsRepository;
	private final EnvelopeBalanceService envelopeBalanceService;
	private final FdtTransactionMapper transactionMapper;
	private final FdtSnapshotAssembler snapshotAssembler;
	private final Clock clock;

	@Transactional(readOnly = true)
	public FdtBootstrap build(long userId) {
		LocalDate asOf = LocalDate.now(clock);
		List<Account> accounts = accountRepository.findAllByUserIdAndManagedTrueOrderByIdAsc(userId);
		List<Card> cards = cardRepository.findAllByUserIdAndManagedTrueOrderByIdAsc(userId);
		List<CardBilling> unpaidBillings = FdtSnapshotAssembler.unpaid(
				cards.isEmpty() ? List.of() : cardBillingRepository.findAllByCardIdIn(
						cards.stream().map(Card::getId).toList()));
		List<FixedExpense> fixedExpenses = fixedExpenseRepository.findAllByUserIdAndActiveTrueOrderByIdAsc(userId);

		int anchorDay = anchorDayOf(userId);
		String month = BudgetPeriod.current(asOf, anchorDay).month();
		List<EnvelopeBalance> balances = envelopeBalanceService.getMonthlyBalances(userId, month);

		FdtSnapshot snapshot = snapshotAssembler.assemble(
				asOf, accounts, cards, unpaidBillings, fixedExpenses, emergencyAmountOf(userId, month), budgets(balances));

		return new FdtBootstrap(
				asOf.toString(),
				transactionMapper.map(
						transactionRepository.findAllByUserIdOrderByTransactionDateAscTransactionTimeAscIdAsc(userId)),
				snapshot,
				envelopes(balances),
				anchorDay
		);
	}

	/** 봉투 한도. 확정되지 않은 봉투는 엔진에 한도가 없는 것으로 둔다. */
	private Map<String, Long> budgets(List<EnvelopeBalance> balances) {
		Map<String, Long> budgets = new LinkedHashMap<>();
		for (EnvelopeBalance balance : balances) {
			if (balance.confirmedAmount() != null) {
				budgets.put(balance.envelopeName(), balance.confirmedAmount());
			}
		}
		return budgets;
	}

	private List<FdtBootstrap.Envelope> envelopes(List<EnvelopeBalance> balances) {
		return balances.stream()
				.filter(balance -> balance.remaining() != null)
				.map(balance -> new FdtBootstrap.Envelope(balance.envelopeName(), balance.remaining()))
				.toList();
	}

	private long emergencyAmountOf(long userId, String month) {
		return budgetRepository.findByUserIdAndBudgetMonth(userId, month)
				.map(Budget::getEmergencyAmount)
				.orElse(0L);
	}

	private int anchorDayOf(long userId) {
		return userSettingsRepository.findById(userId)
				.map(UserSettings::getBudgetAnchorDay)
				.orElse(DEFAULT_ANCHOR_DAY);
	}
}
