package com.finset.key_fin.budget.service;

import com.finset.key_fin.budget.repository.BudgetRepository;
import com.finset.key_fin.user.entity.UserSettings;
import com.finset.key_fin.user.repository.UserSettingsRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.util.Optional;
import java.util.List;

@Service
@RequiredArgsConstructor
public class BudgetOverrunService {
	private final BudgetRepository budgets;
	private final UserSettingsRepository settings;
	private final EnvelopeBalanceService balances;

	/** Current category effects are derived on every read, independently of persistent stickers. */
	public List<Integer> currentExceededEnvelopeIds(long userId, LocalDate today) {
		int anchor = settings.findById(userId).map(UserSettings::getBudgetAnchorDay).orElse(1);
		String month = BudgetPeriod.current(today, anchor).month();
		return budgets.findByUserIdAndBudgetMonth(userId, month).filter(b -> b.isConfirmed())
				.map(b -> balances.getMonthlyBalances(userId, month).stream()
						.filter(balance -> balance.confirmedAmount() != null && balance.spent() > balance.confirmedAmount())
						.map(EnvelopeBalanceService.EnvelopeBalance::envelopeId).toList())
				.orElseGet(List::of);
	}

	/** An absent/unconfirmed budget is distinct from a confirmed budget whose overrun has cleared. */
	public Optional<BudgetOverrun> currentBudgetOverrun(long userId, LocalDate today) {
		int anchor = settings.findById(userId).map(UserSettings::getBudgetAnchorDay).orElse(1);
		String month = BudgetPeriod.current(today, anchor).month();
		return budgets.findByUserIdAndBudgetMonth(userId, month).filter(b -> b.isConfirmed()).map(budget -> {
			long confirmed = 0;
			long spent = 0;
			for (var balance : balances.getMonthlyBalances(userId, month)) {
				confirmed += balance.confirmedAmount();
				spent += balance.spent();
			}
			return new BudgetOverrun(budget.getId(), spent > confirmed);
		});
	}

	public record BudgetOverrun(long budgetId, boolean exceeded) {
	}
}
