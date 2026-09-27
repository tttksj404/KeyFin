package com.finset.key_fin.budget.service;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.Optional;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.transaction.annotation.Transactional;

import com.finset.key_fin.budget.service.EnvelopeBalanceService.EnvelopeBalance;
import com.finset.key_fin.support.SpringIntegrationTestSupport;

@Transactional
@Sql("/sql/envelope-balance-fixture.sql")
class EnvelopeBalanceServiceTest extends SpringIntegrationTestSupport {

	private static final long USER = 999L;
	private static final String MONTH = "202609";

	@Autowired
	private EnvelopeBalanceService service;

	@Test
	@DisplayName("차감 규칙: NONE 전액 + DUTCH 내 몫 + RESTORE 입금은 복원, PENDING·CANCELED·제외 태그·일반 입금·타인·타월 거래는 집계되지 않는다")
	void monthlyBalances() {
		List<EnvelopeBalance> balances = service.getMonthlyBalances(USER, MONTH);

		assertThat(balances).hasSize(3);

		EnvelopeBalance dining = balances.get(0);
		assertThat(dining.envelopeId()).isEqualTo(1);
		assertThat(dining.spent()).isEqualTo(10000 + 12500 - 3000);
		assertThat(dining.remaining()).isEqualTo(300000 - 19500);

		EnvelopeBalance transport = balances.get(1);
		assertThat(transport.spent()).isEqualTo(1400);
		assertThat(transport.remaining()).isEqualTo(100000 - 1400);
	}

	@Test
	@DisplayName("미승인 봉투(confirmed NULL)는 spent만 집계되고 remaining은 null")
	void unconfirmedEnvelope() {
		EnvelopeBalance medical = service.getMonthlyBalances(USER, MONTH).get(2);

		assertThat(medical.confirmedAmount()).isNull();
		assertThat(medical.spent()).isZero();
		assertThat(medical.remaining()).isNull();
	}

	@Test
	@DisplayName("단건 잔액 조회 — 존재하면 값, 예산 없는 월이면 empty")
	void remaining() {
		assertThat(service.getRemaining(USER, MONTH, 1)).contains(280500L);
		assertThat(service.getRemaining(USER, "202501", 1)).isEmpty();
		assertThat(service.getRemaining(USER, MONTH, 3)).isEmpty();
	}

	@Test
	@DisplayName("예산이 없는 월은 빈 리스트")
	void noBudgetMonth() {
		assertThat(service.getMonthlyBalances(USER, "202501")).isEmpty();
	}
}
