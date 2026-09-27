package com.finset.key_fin.budget.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Entity
@Table(name = "budget_envelopes")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class BudgetEnvelope {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@ManyToOne(fetch = FetchType.LAZY, optional = false)
	@JoinColumn(name = "budget_id", nullable = false)
	private Budget budget;

	@Column(name = "envelope_id", nullable = false)
	private Integer envelopeId;

	@Column(name = "proposed_amount", nullable = false)
	private Long proposedAmount;

	@Column(name = "confirmed_amount")
	private Long confirmedAmount;

	public static BudgetEnvelope propose(Budget budget, int envelopeId, long proposedAmount) {
		BudgetEnvelope budgetEnvelope = new BudgetEnvelope();
		budgetEnvelope.budget = budget;
		budgetEnvelope.envelopeId = envelopeId;
		budgetEnvelope.proposedAmount = proposedAmount;
		return budgetEnvelope;
	}

	public void confirm(long confirmedAmount) {
		this.confirmedAmount = confirmedAmount;
	}
}
