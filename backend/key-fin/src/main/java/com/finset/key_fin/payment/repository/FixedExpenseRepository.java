package com.finset.key_fin.payment.repository;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

import com.finset.key_fin.payment.entity.ExpenseType;
import com.finset.key_fin.payment.entity.FixedExpense;

public interface FixedExpenseRepository extends JpaRepository<FixedExpense, Long> {

	List<FixedExpense> findAllByUserIdAndActiveTrueOrderByIdAsc(Long userId);

	Optional<FixedExpense> findByIdAndUserIdAndActiveTrue(Long id, Long userId);

	List<FixedExpense> findAllByUserIdAndFinSubscriptionIdIsNotNull(Long userId);

	boolean existsByUserIdAndActiveTrueAndNameAndExpenseTypeAndAmountAndPaymentDayAndWithdrawalAccountId(
			Long userId, String name, ExpenseType expenseType, Long amount, int paymentDay, Long withdrawalAccountId);
}
