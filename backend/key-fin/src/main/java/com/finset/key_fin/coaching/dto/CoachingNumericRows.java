package com.finset.key_fin.coaching.dto;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/** 위험·가정(what-if) 코칭 답변의 봉투별 구조화 행. 값은 엔진 산출값 그대로다. */
@JsonIgnoreProperties(ignoreUnknown = true)
public record CoachingNumericRows(
		@JsonProperty("mode") String mode,
		@JsonProperty("envelope_spend") List<EnvelopeSpend> envelopeSpend,
		@JsonProperty("budget_risk") List<BudgetRisk> budgetRisk
) {
	@JsonIgnoreProperties(ignoreUnknown = true)
	public record EnvelopeSpend(
			@JsonProperty("envelope") String envelope,
			@JsonProperty("p10_krw") long p10Krw,
			@JsonProperty("p50_krw") long p50Krw,
			@JsonProperty("p90_krw") long p90Krw
	) {
	}

	@JsonIgnoreProperties(ignoreUnknown = true)
	public record BudgetRisk(
			@JsonProperty("envelope") String envelope,
			@JsonProperty("budget_krw") long budgetKrw,
			@JsonProperty("observed_used_krw") long observedUsedKrw,
			@JsonProperty("projected_used_p50_krw") long projectedUsedP50Krw,
			@JsonProperty("p_over_budget") double pOverBudget
	) {
	}
}
