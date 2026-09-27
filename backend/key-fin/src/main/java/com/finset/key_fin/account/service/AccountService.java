package com.finset.key_fin.account.service;

import com.finset.key_fin.account.dto.response.AccountListResponse;
import com.finset.key_fin.account.entity.Account;
import com.finset.key_fin.account.exception.AccountErrorCode;
import com.finset.key_fin.account.repository.AccountRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class AccountService {

	private final UserRepository userRepository;
	private final AccountRepository accountRepository;

	@Transactional(readOnly = true)
	public AccountListResponse getManagedAccounts(long userId) {
		validateActiveUser(userId);

		return AccountListResponse.from(
				accountRepository.findAllByUserIdAndManagedTrueOrderByIdAsc(userId)
		);
	}

	@Transactional
	public void designateIncomeAccount(long userId, long accountId) {
		validateActiveUser(userId);
		Account account = accountRepository.findByIdAndUserId(accountId, userId)
				.orElseThrow(() -> new BusinessException(AccountErrorCode.ACCOUNT_NOT_FOUND));
		if (!account.isManaged()) {
			throw new BusinessException(AccountErrorCode.ACCOUNT_NOT_MANAGED);
		}
		if (account.isIncome()) {
			return;
		}

		accountRepository.findAllByUserIdAndIncomeTrue(userId)
				.forEach(Account::removeIncomeDesignation);
		account.designateAsIncome();
	}

	private void validateActiveUser(long userId) {
		userRepository.findByIdAndDeletedAtIsNull(userId)
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_NOT_FOUND));
	}
}
