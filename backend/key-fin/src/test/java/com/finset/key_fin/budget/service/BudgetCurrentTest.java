package com.finset.key_fin.budget.service;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.LocalDate;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.transaction.annotation.Transactional;

import com.finset.key_fin.budget.dto.response.BudgetCurrentResponse;
import com.finset.key_fin.budget.dto.response.BudgetCurrentResponse.EnvelopeBoard;
import com.finset.key_fin.budget.repository.BudgetRepository;
import com.finset.key_fin.support.SpringIntegrationTestSupport;

@Transactional
@Sql({"/sql/budget-confirm-fixture.sql", "/sql/budget-current-fixture.sql"})
class BudgetCurrentTest extends SpringIntegrationTestSupport {

	private static final long CONFIRMED_USER = 991L;
	private static final long PROPOSED_USER = 993L;
	private static final long USER_WITHOUT_BUDGET = 990L;
	private static final long USER_WITH_ANCHOR_23 = 989L;

	@Autowired
	private BudgetService budgetService;

	@Autowired
	private BudgetRepository budgetRepository;

	@Test
	@DisplayName("확정된 예산은 전체·봉투별 확정액·소비·잔액·잔여율을 돌려주고, 초과는 음수·확정 0은 null 비율")
	void confirmedBoard() {
		BudgetCurrentResponse response = budgetService.getCurrent(CONFIRMED_USER);

		assertThat(response.budgetId()).isEqualTo(9003L);
		assertThat(response.month()).isEqualTo("202609");
		assertThat(response.periodFrom()).isEqualTo(LocalDate.of(2026, 9, 1));
		assertThat(response.periodTo()).isEqualTo(LocalDate.of(2026, 9, 30));
		assertThat(response.status()).isEqualTo("CONFIRMED");
		assertThat(response.total().confirmed()).isEqualTo(780000L);
		assertThat(response.total().spent()).isEqualTo(298000L);
		assertThat(response.total().remaining()).isEqualTo(482000L);
		assertThat(response.total().remainingRate()).isEqualTo(61);
		assertThat(response.envelopes()).hasSize(7);

		EnvelopeBoard dining = response.envelopes().get(0);
		assertThat(dining.proposedAmount()).isNull();
		assertThat(dining.confirmedAmount()).isEqualTo(280000L);
		assertThat(dining.spent()).isEqualTo(148000L);
		assertThat(dining.remaining()).isEqualTo(132000L);
		assertThat(dining.remainingRate()).isEqualTo(47);

		assertThat(response.envelopes().get(1).remainingRate()).isEqualTo(-20);

		EnvelopeBoard medical = response.envelopes().get(2);
		assertThat(medical.confirmedAmount()).isZero();
		assertThat(medical.spent()).isEqualTo(30000L);
		assertThat(medical.remaining()).isEqualTo(-30000L);
		assertThat(medical.remainingRate()).isNull();

		assertThat(response.envelopes())
				.extracting(EnvelopeBoard::confirmedAmount)
				.containsExactly(280000L, 100000L, 0L, 100000L, 100000L, 150000L, 50000L);
	}

	@Test
	@DisplayName("미확정 예산은 확정 화면 복원용 제안액만 돌려주고 소비·잔액은 비워 둔다")
	void proposedBoard() {
		BudgetCurrentResponse response = budgetService.getCurrent(PROPOSED_USER);

		assertThat(response.budgetId()).isEqualTo(9001L);
		assertThat(response.status()).isEqualTo("PROPOSED");
		assertThat(response.total()).isNull();
		assertThat(response.envelopes()).hasSize(7);

		EnvelopeBoard dining = response.envelopes().get(0);
		assertThat(dining.name()).isEqualTo("외식");
		assertThat(dining.proposedAmount()).isEqualTo(300000L);
		assertThat(dining.confirmedAmount()).isNull();
		assertThat(dining.spent()).isNull();
		assertThat(dining.remainingRate()).isNull();
	}

	@Test
	@DisplayName("현재 주기 예산이 없으면 제안을 만들어 PROPOSED로 돌려준다")
	void createsProposalWhenMissing() {
		BudgetCurrentResponse response = budgetService.getCurrent(USER_WITHOUT_BUDGET);

		assertThat(response.status()).isEqualTo("PROPOSED");
		assertThat(response.month()).isEqualTo("202609");
		assertThat(response.budgetId()).isNotNull();
		assertThat(response.envelopes())
				.extracting(EnvelopeBoard::proposedAmount)
				.containsExactly(600000L, 100000L, 100000L, 100000L, 100000L, 150000L, 100000L);
		assertThat(budgetRepository.existsByUserIdAndBudgetMonth(USER_WITHOUT_BUDGET, "202609")).isTrue();
	}

	@Test
	@DisplayName("기준일 23 사용자가 9/10에 조회하면 8/23~9/22 주기(라벨 202608)의 예산을 받는다")
	void currentPeriodFollowsAnchorDay() {
		BudgetCurrentResponse response = budgetService.getCurrent(USER_WITH_ANCHOR_23);

		assertThat(response.month()).isEqualTo("202608");
		assertThat(response.periodFrom()).isEqualTo(LocalDate.of(2026, 8, 23));
		assertThat(response.periodTo()).isEqualTo(LocalDate.of(2026, 9, 22));
		assertThat(response.status()).isEqualTo("PROPOSED");
		assertThat(budgetRepository.existsByUserIdAndBudgetMonth(USER_WITH_ANCHOR_23, "202608")).isTrue();
	}
}
