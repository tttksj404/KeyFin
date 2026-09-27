package com.finset.key_fin.coaching.dto;

import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

/** FDT 자산 현황. 필수는 as_of·source·accounts 이고 나머지는 예측 정확도를 위해 채운다. */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record FdtSnapshot(
		@JsonProperty("as_of") String asOf,
		@JsonProperty("source") String source,
		@JsonProperty("accounts") List<Account> accounts,
		@JsonProperty("cards") List<Card> cards,
		@JsonProperty("known_bills") List<KnownBill> knownBills,
		@JsonProperty("schedules") List<Schedule> schedules,
		@JsonProperty("reserve_krw") long reserveKrw,
		@JsonProperty("budgets") Map<String, Long> budgets,
		@JsonProperty("coverage") Coverage coverage
) {

	public record Account(
			@JsonProperty("account_id") String accountId,
			@JsonProperty("balance_krw") long balanceKrw,
			@JsonProperty("is_income") boolean isIncome
	) {
	}

	public record Card(
			@JsonProperty("card_id") String cardId,
			@JsonProperty("kind") String kind,
			@JsonProperty("settlement_account_id") String settlementAccountId,
			@JsonProperty("opening_payable_krw") long openingPayableKrw,
			@JsonProperty("payment_delay_days") int paymentDelayDays
	) {
	}

	public record KnownBill(
			@JsonProperty("bill_id") String billId,
			@JsonProperty("card_id") String cardId,
			@JsonProperty("due_date") String dueDate,
			@JsonProperty("amount_krw") long amountKrw
	) {
	}

	@JsonInclude(JsonInclude.Include.NON_NULL)
	public record Schedule(
			@JsonProperty("rule_id") String ruleId,
			@JsonProperty("kind") String kind,
			@JsonProperty("amount_krw") long amountKrw,
			@JsonProperty("frequency") String frequency,
			@JsonProperty("next_date") String nextDate,
			@JsonProperty("day_of_month") Integer dayOfMonth,
			@JsonProperty("fixed_group") String fixedGroup,
			@JsonProperty("account_id") String accountId,
			@JsonProperty("card_id") String cardId
	) {
	}

	/** 자산·부채 원금을 보내지 않으므로 둘 다 false. 엔진은 순자산 기능만 degrade 한다. */
	public record Coverage(
			@JsonProperty("all_assets_reported") boolean allAssetsReported,
			@JsonProperty("all_liabilities_reported") boolean allLiabilitiesReported
	) {
		public static final Coverage NONE = new Coverage(false, false);
	}
}
