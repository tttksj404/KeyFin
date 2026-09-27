package com.finset.key_fin.coaching.dto;

import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/** `POST /v1/sessions/{id}/messages` 응답. `answer_type` 이 있으면 ChatAnswer, `receipt` 가 있으면 Coaching. */
@JsonIgnoreProperties(ignoreUnknown = true)
public record CoachingTurnReply(
		@JsonProperty("id") String id,
		@JsonProperty("answer_type") String answerType,
		@JsonProperty("status") String status,
		@JsonProperty("text") String text,
		@JsonProperty("wording_source") String wordingSource,
		@JsonProperty("fallback_reason") String fallbackReason,
		@JsonProperty("receipt") Map<String, Object> receipt,
		@JsonProperty("chart_hint") ChartHint chartHint,
		@JsonProperty("rows") List<SpendingRow> rows,
		@JsonProperty("total_krw") Long totalKrw,
		@JsonProperty("numeric_rows") CoachingNumericRows numericRows,
		@JsonProperty("envelope_balances") List<EnvelopeBalance> envelopeBalances
) {
	/** 봉투 잔액 표가 없는 응답(대부분의 턴)용 생성자. */
	public CoachingTurnReply(String id, String answerType, String status, String text, String wordingSource,
			String fallbackReason, Map<String, Object> receipt, ChartHint chartHint, List<SpendingRow> rows,
			Long totalKrw, CoachingNumericRows numericRows) {
		this(id, answerType, status, text, wordingSource, fallbackReason, receipt, chartHint, rows, totalKrw,
				numericRows, List.of());
	}

	/** 대화 턴에서 봉투가 둘 이상일 때 코칭이 문장 대신 표 행으로 싣는 봉투별 장부 잔액. */
	public record EnvelopeBalance(
			@JsonProperty("envelope") String envelope,
			@JsonProperty("balance_krw") long balanceKrw
	) {
	}

	public boolean isCoaching() {
		return answerType == null && receipt != null;
	}
}
