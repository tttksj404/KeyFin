package com.finset.key_fin.budget.dto.response;

import java.time.LocalDate;
import java.util.List;

public record BudgetCurrentResponse(
		Long budgetId,
		String month,
		LocalDate periodFrom,
		LocalDate periodTo,
		String status,
		Total total,
		List<EnvelopeBoard> envelopes,
		Emergency emergency
) {

	public record Total(long confirmed, long spent, long remaining, Integer remainingRate) {
	}

	/** 가상 풀. amount 0 = 미설정. spent는 주기 내 EMERGENCY 태그 거래 합, remaining = amount − spent(음수 가능). */
	public record Emergency(long amount, long spent, long remaining) {
		public static Emergency of(long amount, long spent) {
			return new Emergency(amount, spent, amount - spent);
		}
	}

	public record EnvelopeBoard(
			int envelopeId,
			String name,
			Long proposedAmount,
			Long confirmedAmount,
			Long spent,
			Long remaining,
			Integer remainingRate
	) {

		public static EnvelopeBoard proposed(int envelopeId, String name, long proposedAmount) {
			return new EnvelopeBoard(envelopeId, name, proposedAmount, null, null, null, null);
		}

		public static EnvelopeBoard confirmed(int envelopeId, String name, long confirmedAmount, long spent,
				long remaining, Integer remainingRate) {
			return new EnvelopeBoard(envelopeId, name, null, confirmedAmount, spent, remaining, remainingRate);
		}
	}
}
