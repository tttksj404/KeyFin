package com.finset.key_fin.coaching.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

/** 코칭 턴 응답의 chart_hint. 그대로 `POST /v1/charts/budget-forecast` 본문이 되므로 endpoint 는 받지 않는다. */
@JsonIgnoreProperties(ignoreUnknown = true)
@JsonInclude(JsonInclude.Include.NON_NULL)
public record ChartHint(
		@JsonProperty("period_start") String periodStart,
		@JsonProperty("question") String question,
		@JsonProperty("purchase") Purchase purchase
) {
	@JsonIgnoreProperties(ignoreUnknown = true)
	public record Purchase(
			@JsonProperty("envelope") String envelope,
			@JsonProperty("amount_krw") long amountKrw,
			@JsonProperty("on_date") String onDate
	) {
	}
}
