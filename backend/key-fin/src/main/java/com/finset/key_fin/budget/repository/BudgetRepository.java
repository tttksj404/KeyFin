package com.finset.key_fin.budget.repository;

import java.util.Optional;

import com.finset.key_fin.budget.entity.Budget;
import org.springframework.data.jpa.repository.JpaRepository;

public interface BudgetRepository extends JpaRepository<Budget, Long> {

	boolean existsByUserId(Long userId);
	boolean existsByUserIdAndBudgetMonth(Long userId, String budgetMonth);

	Optional<Budget> findByIdAndUserId(Long id, Long userId);

	Optional<Budget> findByUserIdAndBudgetMonth(Long userId, String budgetMonth);
}
