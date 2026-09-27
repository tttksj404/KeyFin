package com.finset.key_fin.payment.service;

import java.util.List;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.finset.key_fin.account.entity.Account;
import com.finset.key_fin.account.exception.AccountErrorCode;
import com.finset.key_fin.account.repository.AccountRepository;
import com.finset.key_fin.card.entity.Card;
import com.finset.key_fin.card.repository.CardRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.payment.dto.request.FixedExpenseRequest;
import com.finset.key_fin.payment.dto.response.FixedExpenseIdResponse;
import com.finset.key_fin.payment.dto.response.FixedExpenseResponse;
import com.finset.key_fin.payment.entity.FixedExpense;
import com.finset.key_fin.payment.exception.PaymentErrorCode;
import com.finset.key_fin.payment.repository.FixedExpenseRepository;
import com.finset.key_fin.user.repository.UserRepository;

import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class FixedExpenseService {

	private final FixedExpenseRepository fixedExpenseRepository;
	private final AccountRepository accountRepository;
	private final CardRepository cardRepository;
	private final UserRepository userRepository;

	@Transactional
	public FixedExpenseIdResponse register(long userId, FixedExpenseRequest request) {
		validate(userId, request);
		boolean duplicated = fixedExpenseRepository
				.existsByUserIdAndActiveTrueAndNameAndExpenseTypeAndAmountAndPaymentDayAndWithdrawalAccountId(
						userId, request.name(), request.expenseType(), request.amount(),
						request.paymentDay(), request.withdrawalAccountId());
		if (duplicated) {
			throw new BusinessException(PaymentErrorCode.FIXED_EXPENSE_DUPLICATED);
		}

		FixedExpense expense = fixedExpenseRepository.save(FixedExpense.register(
				userRepository.getReferenceById(userId),
				request.name(), request.expenseType(), request.amount(),
				request.isVariable(), request.paymentDay(), request.withdrawalAccountId()));
		return new FixedExpenseIdResponse(expense.getId());
	}

	@Transactional(readOnly = true)
	public List<FixedExpenseResponse> list(long userId) {
		return fixedExpenseRepository.findAllByUserIdAndActiveTrueOrderByIdAsc(userId).stream()
				.map(FixedExpenseResponse::from)
				.toList();
	}

	@Transactional
	public FixedExpenseIdResponse update(long userId, long fixedExpenseId, FixedExpenseRequest request) {
		FixedExpense expense = findManual(userId, fixedExpenseId);
		validate(userId, request);
		expense.update(request.name(), request.expenseType(), request.amount(),
				request.isVariable(), request.paymentDay(), request.withdrawalAccountId());
		return new FixedExpenseIdResponse(expense.getId());
	}

	@Transactional
	public void delete(long userId, long fixedExpenseId) {
		findManual(userId, fixedExpenseId).deactivate();
	}

	@Transactional
	public FixedExpenseIdResponse assignCard(long userId, long fixedExpenseId, long cardId) {
		FixedExpense expense = fixedExpenseRepository.findByIdAndUserIdAndActiveTrue(fixedExpenseId, userId)
				.orElseThrow(() -> new BusinessException(PaymentErrorCode.FIXED_EXPENSE_NOT_FOUND));
		if (!expense.isSynced()) {
			throw new BusinessException(PaymentErrorCode.FIXED_EXPENSE_NOT_SUBSCRIPTION);
		}
		Card card = cardRepository.findByIdAndUserId(cardId, userId)
				.orElseThrow(() -> new BusinessException(PaymentErrorCode.CARD_NOT_FOUND));
		if (!card.isManaged()) {
			throw new BusinessException(PaymentErrorCode.CARD_NOT_MANAGED);
		}
		expense.assignCard(card.getId());
		return new FixedExpenseIdResponse(expense.getId());
	}

	private FixedExpense findManual(long userId, long fixedExpenseId) {
		FixedExpense expense = fixedExpenseRepository.findByIdAndUserIdAndActiveTrue(fixedExpenseId, userId)
				.orElseThrow(() -> new BusinessException(PaymentErrorCode.FIXED_EXPENSE_NOT_FOUND));
		if (expense.isSynced()) {
			throw new BusinessException(PaymentErrorCode.FIXED_EXPENSE_SYNCED);
		}
		return expense;
	}

	private void validate(long userId, FixedExpenseRequest request) {
		if (!request.expenseType().isManualAllowed()) {
			throw new BusinessException(PaymentErrorCode.EXPENSE_TYPE_NOT_MANUAL);
		}
		Account account = accountRepository.findByIdAndUserId(request.withdrawalAccountId(), userId)
				.orElseThrow(() -> new BusinessException(AccountErrorCode.ACCOUNT_NOT_FOUND));
		if (!account.isManaged()) {
			throw new BusinessException(AccountErrorCode.ACCOUNT_NOT_MANAGED);
		}
	}
}
