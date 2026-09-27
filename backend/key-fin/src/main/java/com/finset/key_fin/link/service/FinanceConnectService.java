package com.finset.key_fin.link.service;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.link.client.FinanceMemberClient;
import com.finset.key_fin.link.dto.request.FinanceConnectRequest;
import com.finset.key_fin.link.dto.response.FinanceConnectResponse;
import com.finset.key_fin.link.dto.response.FinanceMember;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class FinanceConnectService {

	private final UserRepository userRepository;
	private final FinanceMemberClient financeMemberClient;
	private final FinanceConnectWriter financeConnectWriter;

	public FinanceConnectResponse connect(long userId, FinanceConnectRequest request) {
		findActiveUser(userId);

		FinanceMember financeMember = financeMemberClient.findByEmail(request.financeEmail());
		return financeConnectWriter.connect(userId, financeMember.userKey());
	}

	@Transactional(readOnly = true)
	public FinanceConnectResponse getStatus(long userId) {
		User user = findActiveUser(userId);
		return FinanceConnectResponse.of(user.isFinanceConnected());
	}

	private User findActiveUser(long userId) {
		return userRepository.findByIdAndDeletedAtIsNull(userId)
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_NOT_FOUND));
	}
}
