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
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AuthServiceTest {

	private static final long USER_ID = 1L;
	private static final String EMAIL = "qwer@qwer.com";
	private static final String RAW_PASSWORD = "P@ssw0rd!";
	private static final String ENCODED_PASSWORD = "encoded-password";
	private static final String ACCESS_TOKEN = "access-token";
	private static final String REFRESH_TOKEN = "refresh-token";

	private UserRepository userRepository;
	private UserProfileRepository userProfileRepository;
	private UserSettingsRepository userSettingsRepository;
	private PasswordEncoder passwordEncoder;
	private JwtTokenProvider jwtTokenProvider;
	private RefreshTokenRepository refreshTokenRepository;
	private AuthService authService;
	private final DefaultFurnitureService defaultFurnitureService = mock(DefaultFurnitureService.class);

	@BeforeEach
	void setUp() {
		userRepository = mock(UserRepository.class);
		userProfileRepository = mock(UserProfileRepository.class);
		userSettingsRepository = mock(UserSettingsRepository.class);
		passwordEncoder = mock(PasswordEncoder.class);
		jwtTokenProvider = mock(JwtTokenProvider.class);
		refreshTokenRepository = mock(RefreshTokenRepository.class);
		authService = new AuthService(
				userRepository,
				userProfileRepository,
				userSettingsRepository,
				passwordEncoder,
				jwtTokenProvider,
				refreshTokenRepository,
				defaultFurnitureService
		);
	}

	@Test
	void signsUpUserWithProfileAndSettings() {
		User savedUser = mock(User.class);
		when(savedUser.getId()).thenReturn(USER_ID);
		when(userRepository.findByEmail(EMAIL)).thenReturn(Optional.empty());
		when(passwordEncoder.encode(RAW_PASSWORD)).thenReturn(ENCODED_PASSWORD);
		when(userRepository.save(org.mockito.ArgumentMatchers.any(User.class))).thenReturn(savedUser);

		SignupResponse response = authService.signup(new SignupRequest(EMAIL, RAW_PASSWORD, "김예린"));

		assertThat(response.userId()).isEqualTo(USER_ID);
		verify(passwordEncoder).encode(RAW_PASSWORD);
		verify(userProfileRepository).save(org.mockito.ArgumentMatchers.any(UserProfile.class));
		verify(userSettingsRepository).save(org.mockito.ArgumentMatchers.any(UserSettings.class));
		verify(defaultFurnitureService).provision(USER_ID);
	}

	@Test
	void rejectsAlreadyRegisteredEmail() {
		User existingUser = mock(User.class);
		when(existingUser.isDeleted()).thenReturn(false);
		when(userRepository.findByEmail(EMAIL)).thenReturn(Optional.of(existingUser));

		assertSignupError(UserErrorCode.DUPLICATE_EMAIL);
		verify(passwordEncoder, never()).encode(RAW_PASSWORD);
	}

	@Test
	void rejectsDeletedEmailRegistration() {
		User deletedUser = mock(User.class);
		when(deletedUser.isDeleted()).thenReturn(true);
		when(userRepository.findByEmail(EMAIL)).thenReturn(Optional.of(deletedUser));

		assertSignupError(UserErrorCode.DELETED_USER);
		verify(passwordEncoder, never()).encode(RAW_PASSWORD);
	}

	@Test
	void logsInAndStoresRefreshToken() {
		User user = mockUser();
		when(userRepository.findByEmailAndDeletedAtIsNull(EMAIL)).thenReturn(Optional.of(user));
		when(passwordEncoder.matches(RAW_PASSWORD, ENCODED_PASSWORD)).thenReturn(true);
		when(jwtTokenProvider.generateAccessToken(USER_ID)).thenReturn(ACCESS_TOKEN);
		when(jwtTokenProvider.generateRefreshToken(USER_ID)).thenReturn(REFRESH_TOKEN);

		LoginResponse response = authService.login(new LoginRequest(EMAIL, RAW_PASSWORD));

		assertThat(response.accessToken()).isEqualTo(ACCESS_TOKEN);
		assertThat(response.refreshToken()).isEqualTo(REFRESH_TOKEN);
		assertThat(response.user().id()).isEqualTo(USER_ID);
		assertThat(response.user().name()).isEqualTo("김예린");
		verify(refreshTokenRepository).save(USER_ID, REFRESH_TOKEN);
	}

	@Test
	void rejectsUnknownOrDeletedUserWithoutExposingReason() {
		when(userRepository.findByEmailAndDeletedAtIsNull(EMAIL)).thenReturn(Optional.empty());

		assertThatThrownBy(() -> authService.login(new LoginRequest(EMAIL, RAW_PASSWORD)))
				.isInstanceOf(BusinessException.class)
				.extracting(exception -> ((BusinessException) exception).getErrorCode())
				.isEqualTo(AuthErrorCode.INVALID_CREDENTIALS);
		verify(passwordEncoder, never()).matches(RAW_PASSWORD, ENCODED_PASSWORD);
	}

	@Test
	void rejectsWrongPasswordWithoutIssuingToken() {
		User user = mockUser();
		when(userRepository.findByEmailAndDeletedAtIsNull(EMAIL)).thenReturn(Optional.of(user));
		when(passwordEncoder.matches(RAW_PASSWORD, ENCODED_PASSWORD)).thenReturn(false);

		assertThatThrownBy(() -> authService.login(new LoginRequest(EMAIL, RAW_PASSWORD)))
				.isInstanceOf(BusinessException.class)
				.extracting(exception -> ((BusinessException) exception).getErrorCode())
				.isEqualTo(AuthErrorCode.INVALID_CREDENTIALS);
		verify(jwtTokenProvider, never()).generateAccessToken(USER_ID);
	}

	@Test
	void issuesAccessTokenFromStoredRefreshToken() {
		User user = mockUser();
		when(jwtTokenProvider.getUserId(REFRESH_TOKEN, TokenType.REFRESH)).thenReturn(USER_ID);
		when(refreshTokenRepository.matches(USER_ID, REFRESH_TOKEN)).thenReturn(true);
		when(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).thenReturn(Optional.of(user));
		when(jwtTokenProvider.generateAccessToken(USER_ID)).thenReturn(ACCESS_TOKEN);

		AccessTokenResponse response = authService.refresh(new RefreshTokenRequest(REFRESH_TOKEN));

		assertThat(response.accessToken()).isEqualTo(ACCESS_TOKEN);
	}

	@Test
	void logsOutByDeletingStoredRefreshToken() {
		authService.logout(USER_ID);

		verify(refreshTokenRepository).delete(USER_ID);
	}

	@Test
	void rejectsRefreshTokenThatDoesNotMatchRedis() {
		when(jwtTokenProvider.getUserId(REFRESH_TOKEN, TokenType.REFRESH)).thenReturn(USER_ID);
		when(refreshTokenRepository.matches(USER_ID, REFRESH_TOKEN)).thenReturn(false);

		assertInvalidRefreshToken();
		verify(userRepository, never()).findByIdAndDeletedAtIsNull(USER_ID);
	}

	@Test
	void rejectsRefreshTokenForDeletedUser() {
		when(jwtTokenProvider.getUserId(REFRESH_TOKEN, TokenType.REFRESH)).thenReturn(USER_ID);
		when(refreshTokenRepository.matches(USER_ID, REFRESH_TOKEN)).thenReturn(true);
		when(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).thenReturn(Optional.empty());

		assertInvalidRefreshToken();
		verify(jwtTokenProvider, never()).generateAccessToken(USER_ID);
	}

	@Test
	void normalizesExpiredRefreshTokenAsInvalidRefreshToken() {
		when(jwtTokenProvider.getUserId(REFRESH_TOKEN, TokenType.REFRESH))
				.thenThrow(new BusinessException(AuthErrorCode.EXPIRED_TOKEN));

		assertInvalidRefreshToken();
		verify(refreshTokenRepository, never()).matches(USER_ID, REFRESH_TOKEN);
	}

	private User mockUser() {
		User user = mock(User.class);
		when(user.getId()).thenReturn(USER_ID);
		when(user.getPassword()).thenReturn(ENCODED_PASSWORD);
		when(user.getName()).thenReturn("김예린");
		return user;
	}

	private void assertInvalidRefreshToken() {
		assertThatThrownBy(() -> authService.refresh(new RefreshTokenRequest(REFRESH_TOKEN)))
				.isInstanceOf(BusinessException.class)
				.extracting(exception -> ((BusinessException) exception).getErrorCode())
				.isEqualTo(AuthErrorCode.INVALID_REFRESH_TOKEN);
	}

	private void assertSignupError(UserErrorCode errorCode) {
		assertThatThrownBy(() -> authService.signup(new SignupRequest(EMAIL, RAW_PASSWORD, "김예린")))
				.isInstanceOf(BusinessException.class)
				.extracting(exception -> ((BusinessException) exception).getErrorCode())
				.isEqualTo(errorCode);
	}
}
