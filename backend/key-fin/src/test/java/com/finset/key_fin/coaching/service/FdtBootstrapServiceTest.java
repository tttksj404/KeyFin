package com.finset.key_fin.coaching.service;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.test.context.jdbc.SqlConfig;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.finset.key_fin.coaching.dto.FdtBootstrap;
import com.finset.key_fin.coaching.dto.FdtSnapshot;
import com.finset.key_fin.coaching.dto.FdtTransaction;
import com.finset.key_fin.support.SpringIntegrationTestSupport;

@Transactional
@Sql(scripts = "/sql/coaching-bootstrap-fixture.sql", config = @SqlConfig(encoding = "UTF-8"))
class FdtBootstrapServiceTest extends SpringIntegrationTestSupport {

	private static final long USER_ID = 970L;

	@Autowired
	private FdtBootstrapService service;

	private final ObjectMapper objectMapper = new ObjectMapper();

	@Test
	void 원장에서_CARRYOVER와_본인_계좌_이동을_빼고_나머지를_모두_보낸다() {
		FdtBootstrap bootstrap = service.build(USER_ID);

		assertThat(bootstrap.asOf()).isEqualTo("2026-09-10");
		assertThat(bootstrap.budgetStartDay()).isEqualTo(1);
		assertThat(bootstrap.transactions()).hasSize(8);
		assertThat(bootstrap.transactions())
				.extracting(FdtTransaction::merchant)
				.doesNotContain("초기 잔액 설정(시딩)");
		assertThat(bootstrap.transactions())
				.extracting(FdtTransaction::excludeTag)
				.doesNotContain("SELF_TRANSFER");
	}

	@Test
	void 태그별_변환_규칙이_적용된다() {
		Map<String, FdtTransaction> byId = byTransactionId(service.build(USER_ID));

		assertThat(byId.get("9754").transactionType()).isEqualTo("TRANSFER_OUT");
		assertThat(byId).doesNotContainKey("9755");
		assertThat(byId.get("9756").transactionType()).isEqualTo("DEPOSIT");
		assertThat(byId.get("9756").excludeTag()).isEqualTo("NONE");
		assertThat(byId.get("9752").amountKrw()).isEqualTo(100_000L);
		assertThat(byId.get("9758").excludeTag()).isEqualTo("EMERGENCY");
		assertThat(byId.get("9759").status()).isEqualTo("CANCELED");
	}

	@Test
	void 가맹점_식별자가_세_갈래로_나간다() {
		Map<String, FdtTransaction> byId = byTransactionId(service.build(USER_ID));

		assertThat(byId.get("9750").merchantId()).isEqualTo("26");
		assertThat(byId.get("9751").merchantId()).isEqualTo("raw:무명김밥집");
		assertThat(byId.get("9754").merchantId()).isEmpty();
	}

	@Test
	void 마트는_장보기로_나가고_카페는_그대로_나간다() {
		Map<String, FdtTransaction> byId = byTransactionId(service.build(USER_ID));

		assertThat(byId.get("9753").category()).isEqualTo("생활서비스");
		assertThat(byId.get("9753").subcategory()).isEqualTo("장보기");
		assertThat(byId.get("9750").category()).isEqualTo("식비");
		assertThat(byId.get("9750").subcategory()).isEqualTo("카페");
	}

	@Test
	void 연결_해제한_계좌는_스냅샷에_없다() {
		FdtSnapshot snapshot = service.build(USER_ID).snapshot();

		assertThat(snapshot.accounts()).extracting(FdtSnapshot.Account::accountId)
				.containsExactly("9700", "9701");
	}

	@Test
	void 카드_미납액이_청구서_합계와_일치한다() {
		FdtSnapshot snapshot = service.build(USER_ID).snapshot();

		Map<String, Long> billSumByCard = snapshot.knownBills().stream()
				.collect(Collectors.groupingBy(FdtSnapshot.KnownBill::cardId,
						Collectors.summingLong(FdtSnapshot.KnownBill::amountKrw)));
		for (FdtSnapshot.Card card : snapshot.cards()) {
			assertThat(card.openingPayableKrw())
					.isEqualTo(billSumByCard.getOrDefault(card.cardId(), 0L));
		}
		assertThat(billSumByCard).containsEntry("9710", 500_000L);
	}

	@Test
	void 출금_요일이_없는_카드와_그_청구서는_빠진다() {
		FdtSnapshot snapshot = service.build(USER_ID).snapshot();

		assertThat(snapshot.cards()).extracting(FdtSnapshot.Card::cardId).containsExactly("9710", "9711");
		assertThat(snapshot.knownBills()).extracting(FdtSnapshot.KnownBill::billId)
				.containsExactlyInAnyOrder("9720", "9721");
	}

	@Test
	void 고정지출_일정에서_카드대금은_빠지고_대출은_묶음이_비어있다() {
		FdtSnapshot snapshot = service.build(USER_ID).snapshot();

		assertThat(snapshot.schedules()).extracting(FdtSnapshot.Schedule::ruleId)
				.containsExactly("9730", "9731", "9732");
		Map<String, FdtSnapshot.Schedule> byRule = snapshot.schedules().stream()
				.collect(Collectors.toMap(FdtSnapshot.Schedule::ruleId, Function.identity()));
		assertThat(byRule.get("9730").fixedGroup()).isEqualTo("주거");
		assertThat(byRule.get("9731").fixedGroup()).isEqualTo("공과금");
		assertThat(byRule.get("9732").fixedGroup()).isNull();
		assertThat(byRule.get("9732").kind()).isEqualTo("debt_service");
		assertThat(byRule.get("9730").kind()).isEqualTo("fixed_expense");
		assertThat(byRule.get("9730").nextDate()).isEqualTo("2026-10-05");
		assertThat(byRule.get("9731").nextDate()).isEqualTo("2026-09-25");
	}

	@Test
	void 한도는_확정된_봉투만_담고_잔액은_따로_나간다() {
		FdtBootstrap bootstrap = service.build(USER_ID);

		assertThat(bootstrap.snapshot().budgets())
				.containsOnlyKeys("외식", "교통비")
				.containsEntry("외식", 280_000L);
		assertThat(bootstrap.snapshot().reserveKrw()).isEqualTo(300_000L);
		assertThat(bootstrap.envelopes()).extracting(FdtBootstrap.Envelope::envelope)
				.containsExactlyInAnyOrder("외식", "교통비");
	}

	@Test
	void 직렬화하면_엔진_계약_이름으로_나간다() throws Exception {
		String json = objectMapper.writeValueAsString(service.build(USER_ID));

		assertThat(json).contains("\"as_of\"", "\"transaction_type\"", "\"amount_krw\"", "\"exclude_tag\"",
				"\"merchant_id\"", "\"confirm_status\"", "\"known_bills\"", "\"opening_payable_krw\"",
				"\"payment_delay_days\"", "\"reserve_krw\"", "\"balance_krw\"", "\"fixed_group\"", "\"budget_start_day\"");
		assertThat(json).doesNotContain("adjustedAmount", "\"adjusted_amount\"");
	}

	@Test
	void 필수_15개_항목이_모두_들어간다() throws Exception {
		List<String> required = List.of("user_id", "transaction_id", "source", "transaction_type",
				"transaction_date", "transaction_time", "category", "subcategory", "merchant", "merchant_id",
				"amount_krw", "account_id", "card_id", "confirm_status", "status");

		String first = objectMapper.writeValueAsString(service.build(USER_ID).transactions().get(0));

		assertThat(required).allSatisfy(key -> assertThat(first).contains("\"" + key + "\""));
	}

	@Test
	void 생성한_Bootstrap을_파일로_남긴다() throws Exception {
		java.nio.file.Path out = java.nio.file.Path.of(System.getProperty("fdt.bootstrap.out", ""));
		org.junit.jupiter.api.Assumptions.assumeFalse(out.toString().isEmpty());

		objectMapper.writerWithDefaultPrettyPrinter().writeValue(out.toFile(), service.build(USER_ID));

		assertThat(out).exists();
	}

	private Map<String, FdtTransaction> byTransactionId(FdtBootstrap bootstrap) {
		return bootstrap.transactions().stream()
				.collect(Collectors.toMap(FdtTransaction::transactionId, Function.identity()));
	}
}
