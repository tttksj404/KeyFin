package com.finset.key_fin.coaching.dto;

import java.util.List;

public record ChatReply(
		String reply,
		Kind kind,
		String status,
		String source,
		String fallbackReason,
		String answerId,
		String chartId,
		List<Row> rows,
		Long totalKrw,
		NumericRows numericRows,
		List<EnvelopeBalance> envelopeBalances
) {
	public record Row(String envelope, long totalKrw, int count) {
	}

	/** 봉투별 장부 잔액 표 행. 본문에는 표 설명 한 줄만 있다. */
	public record EnvelopeBalance(String envelope, long balanceKrw) {
	}

	public record NumericRows(String mode, List<EnvelopeSpend> envelopeSpend, List<BudgetRisk> budgetRisk) {
		public record EnvelopeSpend(String envelope, long p10Krw, long p50Krw, long p90Krw) {
		}

		public record BudgetRisk(String envelope, long budgetKrw, long observedUsedKrw, long projectedUsedP50Krw,
				double pOverBudget) {
		}

		static NumericRows from(CoachingNumericRows source) {
			if (source == null) {
				return null;
			}
			return new NumericRows(
					source.mode(),
					source.envelopeSpend() == null ? List.of() : source.envelopeSpend().stream()
							.map(row -> new EnvelopeSpend(row.envelope(), row.p10Krw(), row.p50Krw(), row.p90Krw()))
							.toList(),
					source.budgetRisk() == null ? List.of() : source.budgetRisk().stream()
							.map(row -> new BudgetRisk(row.envelope(), row.budgetKrw(), row.observedUsedKrw(),
									row.projectedUsedP50Krw(), row.pOverBudget()))
							.toList());
		}
	}
	public enum Kind { CHAT, COACHING }

	public static ChatReply from(CoachingTurnReply turn, String chartId) {
		boolean coaching = turn.isCoaching();
		List<Row> rows = turn.rows() == null ? List.of() : turn.rows().stream()
				.map(row -> new Row(row.envelope(), row.totalKrw(), row.count()))
				.toList();
		return new ChatReply(
				turn.text(),
				coaching ? Kind.COACHING : Kind.CHAT,
				coaching ? "answered" : turn.status(),
				turn.wordingSource(),
				turn.fallbackReason(),
				turn.id(),
				chartId,
				rows,
				turn.totalKrw(),
				NumericRows.from(turn.numericRows()),
				turn.envelopeBalances() == null ? List.of() : turn.envelopeBalances().stream()
						.map(row -> new EnvelopeBalance(row.envelope(), row.balanceKrw()))
						.toList());
	}
}
