package com.finset.key_fin.user.service;

import com.finset.key_fin.auth.repository.RefreshTokenRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.user.dto.request.AccountDeletionRequest;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.LocalDateTime;

@Service
@RequiredArgsConstructor
public class UserService {

	private final UserRepository userRepository;
	private final PasswordEncoder passwordEncoder;
	private final RefreshTokenRepository refreshTokenRepository;
	private final Clock clock;

	@Transactional
	public void deleteAccount(long userId, AccountDeletionRequest request) {
		User user = userRepository.findByIdAndDeletedAtIsNull(userId)
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_NOT_FOUND));
		if (!passwordEncoder.matches(request.password(), user.getPassword())) {
			throw new BusinessException(UserErrorCode.PASSWORD_MISMATCH);
		}
		user.softDelete(LocalDateTime.now(clock));
		refreshTokenRepository.delete(userId);
	}
}
