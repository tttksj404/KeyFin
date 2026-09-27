package com.finset.key_fin.budget.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import java.util.stream.IntStream;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.transaction.annotation.Transactional;

import com.finset.key_fin.budget.dto.request.BudgetConfirmRequest;
import com.finset.key_fin.budget.dto.request.BudgetConfirmRequest.EnvelopeAmount;
import com.finset.key_fin.budget.dto.response.BudgetConfirmResponse;
import com.finset.key_fin.budget.entity.BudgetEnvelope;
import com.finset.key_fin.budget.exception.BudgetErrorCode;
import com.finset.key_fin.budget.repository.BudgetEnvelopeRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.support.SpringIntegrationTestSupport;

@Transactional
@Sql("/sql/budget-confirm-fixture.sql")
class BudgetConfirmTest extends SpringIntegrationTestSupport {

	private static final long OWNER = 993L;
	private static final long OTHER_USER = 992L;
	private static final long PROPOSED_BUDGET = 9001L;
	private static final long CONFIRMED_BUDGET = 9002L;

	@Autowired
	private BudgetService budgetService;

	@Autowired
	private BudgetEnvelopeRepository budgetEnvelopeRepository;

	@Test
	@DisplayName("봉투 7종의 확정액을 기록하고 CONFIRMED로 전환하며 제안액은 그대로 남긴다")
	void confirmProposedBudget() {
		BudgetConfirmResponse response = budgetService.confirm(OWNER, PROPOSED_BUDGET, requestOf(280000L));

		assertThat(response.budgetId()).isEqualTo(PROPOSED_BUDGET);
		assertThat(response.month()).isEqualTo("202609");
		assertThat(response.status()).isEqualTo("CONFIRMED");

		List<BudgetEnvelope> rows = budgetEnvelopeRepository.findByBudgetId(PROPOSED_BUDGET);
		assertThat(rows).hasSize(7);
		assertThat(rows).filteredOn(row -> row.getEnvelopeId() == 1)
				.singleElement()
				.satisfies(row -> {
					assertThat(row.getProposedAmount()).isEqualTo(300000L);
					assertThat(row.getConfirmedAmount()).isEqualTo(280000L);
				});
		assertThat(rows).filteredOn(row -> row.getEnvelopeId() != 1)
				.extracting(BudgetEnvelope::getConfirmedAmount)
				.containsOnly(100000L);
	}

	@Test
	@DisplayName("이미 확정된 예산은 BUDGET_ALREADY_CONFIRMED")
	void rejectAlreadyConfirmed() {
		assertThatThrownBy(() -> budgetService.confirm(OWNER, CONFIRMED_BUDGET, requestOf(280000L)))
				.isInstanceOf(BusinessException.class)
				.extracting(e -> ((BusinessException) e).getErrorCode())
				.isEqualTo(BudgetErrorCode.BUDGET_ALREADY_CONFIRMED);
	}

	@Test
	@DisplayName("다른 사용자의 예산은 BUDGET_NOT_FOUND")
	void rejectOtherUsersBudget() {
		assertThatThrownBy(() -> budgetService.confirm(OTHER_USER, PROPOSED_BUDGET, requestOf(280000L)))
				.isInstanceOf(BusinessException.class)
				.extracting(e -> ((BusinessException) e).getErrorCode())
				.isEqualTo(BudgetErrorCode.BUDGET_NOT_FOUND);
	}

	@Test
	@DisplayName("봉투가 빠지거나 예산에 없는 봉투가 오면 ENVELOPE_MISMATCH")
	void rejectEnvelopeMismatch() {
		BudgetConfirmRequest missingOne = new BudgetConfirmRequest(
				IntStream.rangeClosed(1, 6).mapToObj(id -> new EnvelopeAmount(id, 100000L)).toList());
		BudgetConfirmRequest unknownEnvelope = new BudgetConfirmRequest(
				IntStream.rangeClosed(2, 8).mapToObj(id -> new EnvelopeAmount(id, 100000L)).toList());

		for (BudgetConfirmRequest request : List.of(missingOne, unknownEnvelope)) {
			assertThatThrownBy(() -> budgetService.confirm(OWNER, PROPOSED_BUDGET, request))
					.isInstanceOf(BusinessException.class)
					.extracting(e -> ((BusinessException) e).getErrorCode())
					.isEqualTo(BudgetErrorCode.ENVELOPE_MISMATCH);
		}
	}

	@Test
	@DisplayName("1,000원 단위가 아닌 금액은 AMOUNT_NOT_THOUSAND_UNIT")
	void rejectNonThousandAmount() {
		assertThatThrownBy(() -> budgetService.confirm(OWNER, PROPOSED_BUDGET, requestOf(280500L)))
				.isInstanceOf(BusinessException.class)
				.extracting(e -> ((BusinessException) e).getErrorCode())
				.isEqualTo(BudgetErrorCode.AMOUNT_NOT_THOUSAND_UNIT);
	}

	private static BudgetConfirmRequest requestOf(long diningAmount) {
		return new BudgetConfirmRequest(IntStream.rangeClosed(1, 7)
				.mapToObj(id -> new EnvelopeAmount(id, id == 1 ? diningAmount : 100000L))
				.toList());
	}
}
