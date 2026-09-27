package com.finset.key_fin.user.service;

import com.finset.key_fin.auth.repository.RefreshTokenRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.user.dto.request.AccountDeletionRequest;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class UserServiceTest {

	private static final long USER_ID = 1L;
	private static final String PASSWORD = "qwer1234@";

	@Mock
	private UserRepository userRepository;
	@Mock
	private PasswordEncoder passwordEncoder;
	@Mock
	private RefreshTokenRepository refreshTokenRepository;

	private UserService userService;

	@BeforeEach
	void setUp() {
		Clock clock = Clock.fixed(
				Instant.parse("2026-09-17T01:00:00Z"),
				ZoneId.of("Asia/Seoul")
		);
		userService = new UserService(userRepository, passwordEncoder, refreshTokenRepository, clock);
	}

	@Test
	void 비밀번호를_확인하고_소프트_삭제한_뒤_리프레시_토큰을_삭제한다() {
		User user = User.create("qwer@qwer.com", "encoded-password", "김예린");
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(passwordEncoder.matches(PASSWORD, "encoded-password")).willReturn(true);

		userService.deleteAccount(USER_ID, new AccountDeletionRequest(PASSWORD));

		assertThat(user.getDeletedAt()).isEqualTo(LocalDateTime.of(2026, 9, 17, 10, 0));
		verify(refreshTokenRepository).delete(USER_ID);
	}

	@Test
	void 현재_비밀번호가_다르면_탈퇴하지_않는다() {
		User user = User.create("qwer@qwer.com", "encoded-password", "김예린");
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(passwordEncoder.matches("wrong-password", "encoded-password")).willReturn(false);

		assertThatThrownBy(() -> userService.deleteAccount(
				USER_ID, new AccountDeletionRequest("wrong-password")))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode()).isEqualTo(UserErrorCode.PASSWORD_MISMATCH));
		assertThat(user.isDeleted()).isFalse();
		verify(refreshTokenRepository, never()).delete(USER_ID);
	}
}
