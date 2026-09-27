package com.finset.key_fin.payment.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.YearMonth;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlConfig;
import org.springframework.transaction.annotation.Transactional;
import com.finset.key_fin.payment.client.FinanceCardBillingClient;
import com.finset.key_fin.payment.dto.response.FinanceBillingStatement;
import com.finset.key_fin.payment.entity.CardBilling;
import com.finset.key_fin.payment.repository.CardBillingRepository;
import com.finset.key_fin.payment.service.CardBillingSyncService.SyncResult;
import com.finset.key_fin.support.SpringIntegrationTestSupport;

@Transactional
@Sql(scripts = "/sql/card-billing-fixture.sql", config = @SqlConfig(encoding = "UTF-8"))
class CardBillingSyncServiceTest extends SpringIntegrationTestSupport {

	private static final long USER = 986L;
	private static final String USER_KEY = "test-user-key-986";
	private static final long CARD = 9601L;
	private static final String CARD_NO = "1001986100000001";
	private static final String CVC = "111";

	@Autowired
	private CardBillingSyncService cardBillingSyncService;
	@Autowired
	private CardBillingRepository cardBillingRepository;

	@Test
	@DisplayName("관리 카드만 청구서 업서트(기존 행 갱신 · 신규 저장), 미관리 카드는 호출하지 않음")
	void syncsManagedCard() {
		when(financeCardBillingClient.findBillingStatements(USER_KEY, CARD_NO, CVC, YearMonth.of(2026, 8), YearMonth.of(2026, 9)))
				.thenReturn(List.of(
						new FinanceBillingStatement("5", "20260831", "120000", "결제완료", "20260902", "160000"),
						new FinanceBillingStatement("1", "20260907", "42000", "결제완료", "20260909", "160000")));

		SyncResult result = cardBillingSyncService.sync(USER);

		assertThat(result.connected()).isTrue();
		assertThat(result.created()).isEqualTo(1);
		assertThat(result.updated()).isEqualTo(1);

		List<CardBilling> billings = cardBillingRepository.findAllByCardIdIn(List.of(CARD));
		assertThat(billings).extracting(CardBilling::getBillingDate)
				.containsExactlyInAnyOrder(LocalDate.of(2026, 8, 31), LocalDate.of(2026, 9, 7));
		CardBilling updated = billings.stream().filter(b -> b.getId() == 9801L).findFirst().orElseThrow();
		assertThat(updated.isPaid()).isTrue();
		assertThat(updated.getPaidAt()).isEqualTo(LocalDateTime.of(2026, 9, 9, 16, 0));
		assertThat(updated.withdrawalDate(3)).isEqualTo(LocalDate.of(2026, 9, 9));
		verify(financeCardBillingClient, never()).findBillingStatements(any(), eq("1001986100000002"), any(), any(), any());
	}

	@Test
	@DisplayName("금융망 미연결 사용자는 호출 없이 NOT_CONNECTED")
	void notConnected() {
		SyncResult result = cardBillingSyncService.sync(985L);

		assertThat(result.connected()).isFalse();
		verify(financeCardBillingClient, never()).findBillingStatements(any(), any(), any(), any(), any());
	}
}
