package com.finset.key_fin.link.service;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.link.dto.response.FinanceConnectResponse;
import com.finset.key_fin.link.exception.LinkErrorCode;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class FinanceConnectWriter {

	private final UserRepository userRepository;

	@Transactional
	public FinanceConnectResponse connect(long userId, String finUserKey) {
		User user = userRepository.findByIdAndDeletedAtIsNull(userId)
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_NOT_FOUND));

		if (userRepository.existsByFinUserKeyAndIdNot(finUserKey, userId)) {
			throw new BusinessException(LinkErrorCode.FINANCE_MEMBER_ALREADY_LINKED);
		}
		user.connectFinance(finUserKey);

		return FinanceConnectResponse.of(true);
	}
}
