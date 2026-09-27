package com.finset.key_fin.budget.repository;

import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

import com.finset.key_fin.budget.entity.BudgetAlertState;

public interface BudgetAlertStateRepository extends JpaRepository<BudgetAlertState, Long> {

	Optional<BudgetAlertState> findByBudgetIdAndEnvelopeId(Long budgetId, Integer envelopeId);
}
