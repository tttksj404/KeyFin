package com.finset.key_fin.coaching.dto;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;

/** 엔진에 Twin 을 세우는 최초 입력. 거래 1~10,000건, 봉투 최대 7개. */
public record FdtBootstrap(
		@JsonProperty("as_of") String asOf,
		@JsonProperty("transactions") List<FdtTransaction> transactions,
		@JsonProperty("snapshot") FdtSnapshot snapshot,
		@JsonProperty("envelopes") List<Envelope> envelopes,
		@JsonProperty("budget_start_day") Integer budgetStartDay
) {

	public record Envelope(
			@JsonProperty("envelope") String envelope,
			@JsonProperty("balance_krw") long balanceKrw
	) {
	}
}
