package com.finset.key_fin.budget.repository;

import java.util.List;

import com.finset.key_fin.budget.entity.BudgetEnvelope;
import org.springframework.data.jpa.repository.JpaRepository;

public interface BudgetEnvelopeRepository extends JpaRepository<BudgetEnvelope, Long> {

	List<BudgetEnvelope> findByBudgetId(Long budgetId);
}
