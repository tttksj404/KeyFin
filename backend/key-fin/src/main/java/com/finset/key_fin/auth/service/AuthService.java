package com.finset.key_fin.auth.service;

import com.finset.key_fin.auth.dto.request.LoginRequest;
import com.finset.key_fin.auth.dto.request.RefreshTokenRequest;
import com.finset.key_fin.auth.dto.request.SignupRequest;
import com.finset.key_fin.auth.dto.response.AccessTokenResponse;
import com.finset.key_fin.auth.dto.response.LoginResponse;
import com.finset.key_fin.auth.dto.response.SignupResponse;
import com.finset.key_fin.auth.exception.AuthErrorCode;
import com.finset.key_fin.auth.jwt.JwtTokenProvider;
import com.finset.key_fin.auth.jwt.TokenType;
import com.finset.key_fin.auth.repository.RefreshTokenRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.furniture.service.DefaultFurnitureService;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.entity.UserProfile;
import com.finset.key_fin.user.entity.UserSettings;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserProfileRepository;
import com.finset.key_fin.user.repository.UserRepository;
import com.finset.key_fin.user.repository.UserSettingsRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class AuthService {

	private final UserRepository userRepository;
	private final UserProfileRepository userProfileRepository;
	private final UserSettingsRepository userSettingsRepository;
	private final PasswordEncoder passwordEncoder;
	private final JwtTokenProvider jwtTokenProvider;
	private final RefreshTokenRepository refreshTokenRepository;
	private final DefaultFurnitureService defaultFurnitureService;

	@Transactional
	public SignupResponse signup(SignupRequest request) {
		validateAvailableEmail(request.email());

		User user = User.create(
				request.email(),
				passwordEncoder.encode(request.password()),
				request.name()
		);
		User savedUser = userRepository.save(user);
		userProfileRepository.save(UserProfile.create(savedUser));
		userSettingsRepository.save(UserSettings.create(savedUser));
		defaultFurnitureService.provision(savedUser.getId());

		return new SignupResponse(savedUser.getId());
	}

	public LoginResponse login(LoginRequest request) {
		User user = userRepository.findByEmailAndDeletedAtIsNull(request.email())
				.orElseThrow(() -> new BusinessException(AuthErrorCode.INVALID_CREDENTIALS));

		if (!passwordEncoder.matches(request.password(), user.getPassword())) {
			throw new BusinessException(AuthErrorCode.INVALID_CREDENTIALS);
		}

		String accessToken = jwtTokenProvider.generateAccessToken(user.getId());
		String refreshToken = jwtTokenProvider.generateRefreshToken(user.getId());
		refreshTokenRepository.save(user.getId(), refreshToken);

		return new LoginResponse(
				accessToken,
				refreshToken,
				new LoginResponse.UserSummary(user.getId(), user.getName())
		);
	}

	public AccessTokenResponse refresh(RefreshTokenRequest request) {
		String refreshToken = request.refreshToken();
		long userId = getRefreshTokenUserId(refreshToken);

		if (!refreshTokenRepository.matches(userId, refreshToken)) {
			throw new BusinessException(AuthErrorCode.INVALID_REFRESH_TOKEN);
		}

		userRepository.findByIdAndDeletedAtIsNull(userId)
				.orElseThrow(() -> new BusinessException(AuthErrorCode.INVALID_REFRESH_TOKEN));

		return new AccessTokenResponse(jwtTokenProvider.generateAccessToken(userId));
	}

	public void logout(long userId) {
		refreshTokenRepository.delete(userId);
	}

	private long getRefreshTokenUserId(String refreshToken) {
		try {
			return jwtTokenProvider.getUserId(refreshToken, TokenType.REFRESH);
		} catch (BusinessException exception) {
			throw new BusinessException(AuthErrorCode.INVALID_REFRESH_TOKEN, exception);
		}
	}

	private void validateAvailableEmail(String email) {
		userRepository.findByEmail(email).ifPresent(user -> {
			if (user.isDeleted()) {
				throw new BusinessException(UserErrorCode.DELETED_USER);
			}
			throw new BusinessException(UserErrorCode.DUPLICATE_EMAIL);
		});
	}
}
