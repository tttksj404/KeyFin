package com.finset.key_fin.budget.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.transaction.annotation.Transactional;
import com.finset.key_fin.budget.dto.request.EmergencyFundRequest;
import com.finset.key_fin.budget.dto.response.BudgetCurrentResponse.Emergency;
import com.finset.key_fin.budget.dto.response.EmergencyFundResponse;
import com.finset.key_fin.budget.exception.BudgetErrorCode;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.support.SpringIntegrationTestSupport;

@Transactional
@Sql({"/sql/budget-confirm-fixture.sql", "/sql/budget-current-fixture.sql"})
class BudgetEmergencyTest extends SpringIntegrationTestSupport {

	private static final long CONFIRMED_USER = 991L;
	private static final long CONFIRMED_BUDGET = 9003L;
	private static final long PROPOSED_USER = 993L;
	private static final long PROPOSED_BUDGET = 9001L;

	@Autowired
	private BudgetService budgetService;
	@Autowired
	private JdbcTemplate jdbcTemplate;

	@Test
	@DisplayName("설정 저장 후 재조회가 일치하고, 사용액은 주기 내 NORMAL·확정 EMERGENCY 거래 합, 잔액은 설정액 − 사용액. 0으로 해제하면 음수 잔액")
	void savesAndReadsBack() {
		assertThat(budgetService.getCurrent(CONFIRMED_USER).emergency()).isEqualTo(new Emergency(0, 0, 0));
		insertEmergencyTx(8801, 45000, "2026-09-08", "NORMAL", "CONFIRMED");
		insertEmergencyTx(8802, 10000, "2026-09-09", "CANCELED", "CONFIRMED");
		insertEmergencyTx(8803, 20000, "2026-08-30", "NORMAL", "CONFIRMED");
		insertEmergencyTx(8804, 7000, "2026-09-09", "NORMAL", "PENDING");

		EmergencyFundResponse saved = budgetService.updateEmergency(
				CONFIRMED_USER, CONFIRMED_BUDGET, new EmergencyFundRequest(200000L));

		assertThat(saved.budgetId()).isEqualTo(CONFIRMED_BUDGET);
		assertThat(saved.emergency()).isEqualTo(new Emergency(200000, 45000, 155000));
		assertThat(budgetService.getCurrent(CONFIRMED_USER).emergency()).isEqualTo(saved.emergency());
		assertThat(budgetService.getCurrent(CONFIRMED_USER).total().spent()).isEqualTo(298000L);

		EmergencyFundResponse cleared = budgetService.updateEmergency(
				CONFIRMED_USER, CONFIRMED_BUDGET, new EmergencyFundRequest(0L));
		assertThat(cleared.emergency()).isEqualTo(new Emergency(0, 45000, -45000));
	}

	@Test
	@DisplayName("미확정(PROPOSED) 예산에도 설정할 수 있고 현재 예산 응답에 함께 실린다")
	void allowsOnProposedBudget() {
		budgetService.updateEmergency(PROPOSED_USER, PROPOSED_BUDGET, new EmergencyFundRequest(100000L));

		var current = budgetService.getCurrent(PROPOSED_USER);
		assertThat(current.status()).isEqualTo("PROPOSED");
		assertThat(current.emergency()).isEqualTo(new Emergency(100000, 0, 100000));
	}

	@Test
	@DisplayName("1,000원 단위가 아니면 BUDGET_005, 남의 예산은 BUDGET_002, 저장은 일어나지 않는다")
	void rejectsUnitAndOwner() {
		assertThatThrownBy(() -> budgetService.updateEmergency(CONFIRMED_USER, CONFIRMED_BUDGET, new EmergencyFundRequest(1500L)))
				.isInstanceOf(BusinessException.class)
				.extracting(e -> ((BusinessException) e).getErrorCode()).isEqualTo(BudgetErrorCode.AMOUNT_NOT_THOUSAND_UNIT);
		assertThatThrownBy(() -> budgetService.updateEmergency(992L, CONFIRMED_BUDGET, new EmergencyFundRequest(1000L)))
				.isInstanceOf(BusinessException.class)
				.extracting(e -> ((BusinessException) e).getErrorCode()).isEqualTo(BudgetErrorCode.BUDGET_NOT_FOUND);

		assertThat(budgetService.getCurrent(CONFIRMED_USER).emergency().amount()).isZero();
	}

	private void insertEmergencyTx(long id, long amount, String date, String status, String confirmStatus) {
		jdbcTemplate.update("INSERT INTO transactions (id, user_id, source, tx_type, amount, tx_date, tx_time, subcategory_id, "
				+ "confirm_status, exclude_tag, adjusted_amount, status) VALUES (?, ?, 'SEED', 'CARD', ?, ?, '12:00:00', 101, ?, 'EMERGENCY', NULL, ?)",
				id, CONFIRMED_USER, amount, date, confirmStatus, status);
	}
}
