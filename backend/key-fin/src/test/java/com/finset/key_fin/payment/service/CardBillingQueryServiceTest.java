package com.finset.key_fin.payment.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

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
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.exception.CommonErrorCode;
import com.finset.key_fin.payment.dto.response.CardBillingDetailResponse;
import com.finset.key_fin.payment.dto.response.CardBillingDetailResponse.Approval;
import com.finset.key_fin.payment.dto.response.CardBillingSummaryResponse;
import com.finset.key_fin.payment.dto.response.CardBillingSummaryResponse.CardSummary;
import com.finset.key_fin.payment.dto.response.CardBillingSummaryResponse.Statement;
import com.finset.key_fin.payment.entity.CardBilling.BillingStatus;
import com.finset.key_fin.payment.exception.PaymentErrorCode;
import com.finset.key_fin.support.SpringIntegrationTestSupport;

@Transactional
@Sql(scripts = "/sql/card-billing-fixture.sql", config = @SqlConfig(encoding = "UTF-8"))
class CardBillingQueryServiceTest extends SpringIntegrationTestSupport {

	private static final long USER = 986L;
	private static final long CARD_WITH_WEEKDAY = 9603L;
	private static final long CARD_WITHOUT_WEEKDAY = 9601L;

	@Autowired
	private CardBillingQueryService cardBillingQueryService;
	@Autowired
	private PaymentCalendarService paymentCalendarService;

	@Test
	@DisplayName("목록: 관리 카드만, 이번 주(월~오늘) LIVE 승인 합계·건수와 예정 출금일, 최근 청구서. 출금 요일 없는 카드는 출금일 null")
	void summarizesManagedCards() {
		CardBillingSummaryResponse response = cardBillingQueryService.summary(USER);

		assertThat(response.asOf()).isEqualTo(LocalDate.of(2026, 9, 10));
		assertThat(response.cycleFrom()).isEqualTo(LocalDate.of(2026, 9, 7));
		assertThat(response.nextBillingDate()).isEqualTo(LocalDate.of(2026, 9, 14));
		assertThat(response.cards()).extracting(CardSummary::cardId).containsExactly(CARD_WITHOUT_WEEKDAY, CARD_WITH_WEEKDAY);

		CardSummary shinhan = response.cards().get(1);
		assertThat(shinhan.estimated().amount()).isEqualTo(15000L);
		assertThat(shinhan.estimated().approvalCount()).isEqualTo(2);
		assertThat(shinhan.estimated().withdrawalDate()).isEqualTo(LocalDate.of(2026, 9, 16));
		assertThat(shinhan.withdrawalAccountId()).isEqualTo(9504L);
		Statement latest = shinhan.latestStatement();
		assertThat(latest.billingId()).isEqualTo(9802L);
		assertThat(latest.status()).isEqualTo(BillingStatus.UNPAID);
		assertThat(latest.withdrawalDate()).isEqualTo(LocalDate.of(2026, 9, 9));

		CardSummary legacy = response.cards().get(0);
		assertThat(legacy.withdrawalWeekday()).isNull();
		assertThat(legacy.estimated().amount()).isZero();
		assertThat(legacy.estimated().approvalCount()).isZero();
		assertThat(legacy.estimated().withdrawalDate()).isNull();
		assertThat(legacy.latestStatement().billingId()).isEqualTo(9801L);
		assertThat(legacy.latestStatement().withdrawalDate()).isNull();
	}

	@Test
	@DisplayName("예정액은 캘린더의 CARD_BILL 예상 항목과 같은 값이다")
	void matchesCalendarEstimate() {
		long calendarEstimate = paymentCalendarService.judgedEntries(USER, YearMonth.of(2026, 9)).stream()
				.filter(entry -> entry.item().estimated() && Long.valueOf(CARD_WITH_WEEKDAY).equals(entry.item().cardId()))
				.mapToLong(entry -> entry.item().amount())
				.sum();

		long summaryEstimate = cardBillingQueryService.summary(USER).cards().get(1).estimated().amount();

		assertThat(summaryEstimate).isEqualTo(calendarEstimate).isEqualTo(15000L);
	}

	@Test
	@DisplayName("상세: 근거 승인은 최신순(취소·SEED·지난주 제외), 청구서는 기본 전월~이번 달 최신순, 범위를 주면 그 발행 월만")
	void detailsApprovalsAndStatements() {
		CardBillingDetailResponse detail = cardBillingQueryService.detail(USER, CARD_WITH_WEEKDAY, null, null);

		assertThat(detail.from()).isEqualTo("202608");
		assertThat(detail.to()).isEqualTo("202609");
		assertThat(detail.estimated().amount()).isEqualTo(15000L);
		assertThat(detail.estimated().withdrawalDate()).isEqualTo(LocalDate.of(2026, 9, 16));
		assertThat(detail.estimated().approvals()).extracting(Approval::transactionId).containsExactly(9902L, 9901L);
		assertThat(detail.estimated().approvals()).extracting(Approval::amount).containsExactly(6000L, 9000L);
		assertThat(detail.statements()).extracting(Statement::billingId).containsExactly(9802L, 9803L);
		Statement paid = detail.statements().get(1);
		assertThat(paid.status()).isEqualTo(BillingStatus.PAID);
		assertThat(paid.paidAt()).isEqualTo(LocalDateTime.of(2026, 9, 2, 16, 0));
		assertThat(paid.withdrawalDate()).isEqualTo(LocalDate.of(2026, 9, 2));

		CardBillingDetailResponse september = cardBillingQueryService.detail(USER, CARD_WITH_WEEKDAY, "202609", "202609");
		assertThat(september.statements()).extracting(Statement::billingId).containsExactly(9802L);
		assertThat(cardBillingQueryService.detail(USER, CARD_WITH_WEEKDAY, "202601", "202607").statements()).isEmpty();
	}

	@Test
	@DisplayName("상세: 남의 카드는 404 PAY_013, 잘못된 범위(형식·역순·12개월 초과)는 COMMON_001")
	void rejectsOthersCardAndBadRange() {
		assertThatThrownBy(() -> cardBillingQueryService.detail(985L, CARD_WITH_WEEKDAY, null, null))
				.isInstanceOf(BusinessException.class)
				.extracting(e -> ((BusinessException) e).getErrorCode()).isEqualTo(PaymentErrorCode.CARD_NOT_FOUND);

		for (String[] range : List.of(
				new String[] {"2026-08", null},
				new String[] {"202610", "202609"},
				new String[] {"202509", "202609"})) {
			assertThatThrownBy(() -> cardBillingQueryService.detail(USER, CARD_WITH_WEEKDAY, range[0], range[1]))
					.isInstanceOf(BusinessException.class)
					.extracting(e -> ((BusinessException) e).getErrorCode()).isEqualTo(CommonErrorCode.INVALID_INPUT_VALUE);
		}
		assertThat(cardBillingQueryService.detail(USER, CARD_WITH_WEEKDAY, "202510", "202609").to()).isEqualTo("202609");
	}
}
