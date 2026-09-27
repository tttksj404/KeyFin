package com.finset.key_fin.budget.service;

import com.finset.key_fin.budget.entity.Budget;
import com.finset.key_fin.budget.repository.BudgetRepository;
import com.finset.key_fin.budget.service.EnvelopeBalanceService.EnvelopeBalance;
import com.finset.key_fin.user.entity.UserSettings;
import com.finset.key_fin.user.repository.UserSettingsRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

class BudgetOverrunServiceTest {
	private final BudgetRepository budgets = mock(BudgetRepository.class);
	private final UserSettingsRepository settings = mock(UserSettingsRepository.class);
	private final EnvelopeBalanceService balances = mock(EnvelopeBalanceService.class);
	private final BudgetOverrunService service = new BudgetOverrunService(budgets, settings, balances);
	private final LocalDate today = LocalDate.of(2026, 9, 18);

	@ParameterizedTest
	@CsvSource({"1001,1000,1", "1000,1001,4", "1001,1001,14", "1000,1000,0", "0,0,0"})
	void computesEachEnvelopeIndependently(long food, long leisure, int expected) {
		confirmed("202609");
		when(balances.getMonthlyBalances(1L, "202609")).thenReturn(List.of(
				new EnvelopeBalance(1, "외식", 1000L, food), new EnvelopeBalance(4, "취미·여가", 1000L, leisure)));
		assertThat(service.currentExceededEnvelopeIds(1, today)).isEqualTo(switch (expected) {
			case 1 -> List.of(1); case 4 -> List.of(4); case 14 -> List.of(1, 4); default -> List.of();
		});
	}

	@Test
	void zeroBudgetPositiveSpendExceedsButZeroSpendAndNullBudgetDoNot() {
		confirmed("202609");
		when(balances.getMonthlyBalances(1L, "202609")).thenReturn(List.of(
				new EnvelopeBalance(1, "외식", 0L, 1), new EnvelopeBalance(4, "취미·여가", 0L, 0),
				new EnvelopeBalance(5, "쇼핑", 1L, 2), new EnvelopeBalance(7, "기타", null, 100)));
		assertThat(service.currentExceededEnvelopeIds(1, today)).containsExactly(1, 5);
	}

	@Test
	void missingOrProposedBudgetDoesNotAggregateOrCreateProposal() {
		assertThat(service.currentExceededEnvelopeIds(1, today)).isEmpty();
		when(budgets.findByUserIdAndBudgetMonth(1L, "202609")).thenReturn(Optional.of(Budget.propose(null, "202609")));
		assertThat(service.currentExceededEnvelopeIds(1, today)).isEmpty();
		verifyNoInteractions(balances);
		verify(budgets, never()).save(any());
	}

	@Test
	void readsFreshBalancesAndChangesBudgetAtAnchorDay() {
		var userSettings = mock(UserSettings.class);
		when(userSettings.getBudgetAnchorDay()).thenReturn(23);
		when(settings.findById(1L)).thenReturn(Optional.of(userSettings));
		confirmed("202608");
		when(balances.getMonthlyBalances(1L, "202608"))
				.thenReturn(List.of(new EnvelopeBalance(1, "외식", 1000L, 1001)))
				.thenReturn(List.of(new EnvelopeBalance(1, "외식", 1000L, 1000)));
		assertThat(service.currentExceededEnvelopeIds(1, LocalDate.of(2026, 9, 22))).containsExactly(1);
		assertThat(service.currentExceededEnvelopeIds(1, LocalDate.of(2026, 9, 22))).isEmpty();
		assertThat(service.currentExceededEnvelopeIds(1, LocalDate.of(2026, 9, 23))).isEmpty();
		verify(budgets).findByUserIdAndBudgetMonth(1L, "202609");
	}

	private void confirmed(String month) {
		var budget = Budget.propose(null, month);
		budget.confirm();
		when(budgets.findByUserIdAndBudgetMonth(1L, month)).thenReturn(Optional.of(budget));
	}
}
