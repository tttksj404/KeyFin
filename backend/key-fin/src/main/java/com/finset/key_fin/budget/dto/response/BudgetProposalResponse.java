package com.finset.key_fin.budget.dto.response;

import java.util.List;

public record BudgetProposalResponse(
		Long budgetId,
		String month,
		String status,
		String basis,
		List<EnvelopeProposal> envelopes
) {

	public record EnvelopeProposal(int envelopeId, String name, long proposedAmount, long monthlyAvg) {
	}
}
