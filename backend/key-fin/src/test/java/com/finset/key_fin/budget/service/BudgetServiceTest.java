package com.finset.key_fin.budget.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.transaction.annotation.Transactional;

import com.finset.key_fin.budget.dto.response.BudgetProposalResponse;
import com.finset.key_fin.budget.dto.response.BudgetProposalResponse.EnvelopeProposal;
import com.finset.key_fin.budget.exception.BudgetErrorCode;
import com.finset.key_fin.budget.repository.BudgetEnvelopeRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.support.SpringIntegrationTestSupport;

@Transactional
@Sql("/sql/budget-proposal-fixture.sql")
class BudgetServiceTest extends SpringIntegrationTestSupport {

	private static final long USER_WITH_HISTORY = 997L;
	private static final long USER_WITHOUT_HISTORY = 996L;
	private static final long USER_WITH_SHORT_HISTORY = 995L;
	private static final long USER_WITH_ANCHOR_25 = 994L;
	private static final long USER_WITH_SEEDED_GAP = 988L;

	@Autowired
	private BudgetService budgetService;

	@Autowired
	private BudgetEnvelopeRepository budgetEnvelopeRepository;

	@Test
	@DisplayName("마지막 거래일 기준 직전 3개월 순소비를 일수 비례 월평균으로 환산해 현재 주기에 봉투 7종 전부 제안한다")
	void proposeFromRecentAverage() {
		BudgetProposalResponse response = budgetService.propose(USER_WITH_HISTORY);

		assertThat(response.month()).isEqualTo("202609");
		assertThat(response.status()).isEqualTo("PROPOSED");
		assertThat(response.basis()).isEqualTo("최근 3개월 평균 (2026-06-02~2026-09-01)");
		assertThat(response.envelopes()).hasSize(7);

		EnvelopeProposal dining = response.envelopes().get(0);
		assertThat(dining.monthlyAvg()).isEqualTo(120652);
		assertThat(dining.proposedAmount()).isEqualTo(121000);

		EnvelopeProposal transport = response.envelopes().get(1);
		assertThat(transport.monthlyAvg()).isEqualTo(32608);
		assertThat(transport.proposedAmount()).isEqualTo(33000);

		assertThat(response.envelopes().get(2).proposedAmount()).isZero();
		assertThat(budgetEnvelopeRepository.findAll())
				.filteredOn(row -> row.getBudget().getId().equals(response.budgetId()))
				.hasSize(7);
	}

	@Test
	@DisplayName("이력이 한 달 미만이면 확대 없이 그대로 평균으로 쓴다 (하한 30일)")
	void proposeFromShortHistory() {
		BudgetProposalResponse response = budgetService.propose(USER_WITH_SHORT_HISTORY);

		assertThat(response.basis()).isEqualTo("최근 1개월 평균 (2026-08-15~2026-08-15)");
		assertThat(response.envelopes().get(0).monthlyAvg()).isEqualTo(90000);
		assertThat(response.envelopes().get(0).proposedAmount()).isEqualTo(90000);
	}

	@Test
	@DisplayName("기준일 25 사용자는 현재 주기 라벨이 전월(202608)이고, 마지막 거래 이후 공백은 커버 일수에서 빠진다")
	void proposeForAnchor25UserWithFractionalHistory() {
		BudgetProposalResponse response = budgetService.propose(USER_WITH_ANCHOR_25);

		assertThat(response.month()).isEqualTo("202608");
		assertThat(response.basis()).isEqualTo("최근 1개월 평균 (2026-06-25~2026-08-01)");
		assertThat(response.envelopes().get(0).monthlyAvg()).isEqualTo(181578);
		assertThat(response.envelopes().get(0).proposedAmount()).isEqualTo(182000);
	}

	@Test
	@DisplayName("시딩처럼 최근 구간이 비어 있으면 마지막 거래일까지의 3개월을 그대로 써서 공백만큼 평균이 깎이지 않는다")
	void proposeUsesLatestTransactionWindow() {
		BudgetProposalResponse response = budgetService.propose(USER_WITH_SEEDED_GAP);

		assertThat(response.month()).isEqualTo("202609");
		assertThat(response.basis()).isEqualTo("최근 3개월 평균 (2026-06-01~2026-08-31)");
		assertThat(response.envelopes().get(0).monthlyAvg()).isEqualTo(97826);
		assertThat(response.envelopes().get(0).proposedAmount()).isEqualTo(98000);
	}

	@Test
	@DisplayName("이력이 없으면 기본 템플릿(합계 125만)으로 제안한다")
	void proposeFromDefaultTemplate() {
		BudgetProposalResponse response = budgetService.propose(USER_WITHOUT_HISTORY);

		assertThat(response.basis()).isEqualTo("기본 템플릿");
		assertThat(response.envelopes())
				.extracting(EnvelopeProposal::proposedAmount)
				.containsExactly(600000L, 100000L, 100000L, 100000L, 100000L, 150000L, 100000L);
	}

	@Test
	@DisplayName("현재 주기의 제안이 이미 있으면 BUDGET_ALREADY_EXISTS")
	void rejectDuplicateProposal() {
		budgetService.propose(USER_WITH_HISTORY);

		assertThatThrownBy(() -> budgetService.propose(USER_WITH_HISTORY))
				.isInstanceOf(BusinessException.class)
				.extracting(e -> ((BusinessException) e).getErrorCode())
				.isEqualTo(BudgetErrorCode.BUDGET_ALREADY_EXISTS);
	}
}
