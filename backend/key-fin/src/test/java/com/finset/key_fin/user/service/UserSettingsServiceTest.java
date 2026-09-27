package com.finset.key_fin.user.service;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.user.dto.request.CoachPersonaUpdateRequest;
import com.finset.key_fin.user.dto.request.NotificationSettingsUpdateRequest;
import com.finset.key_fin.user.dto.request.TransferSettingsUpdateRequest;
import com.finset.key_fin.user.dto.response.CoachPersonaResponse;
import com.finset.key_fin.user.dto.response.NotificationSettingsResponse;
import com.finset.key_fin.user.dto.response.TransferSettingsResponse;
import com.finset.key_fin.user.entity.CoachPersona;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.entity.UserSettings;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import com.finset.key_fin.user.repository.UserSettingsRepository;
import org.junit.jupiter.api.BeforeEach;
import com.finset.key_fin.budget.repository.BudgetRepository;
import com.finset.key_fin.user.dto.request.BudgetSettingsUpdateRequest;
import com.finset.key_fin.user.dto.response.BudgetSettingsResponse;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalTime;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class UserSettingsServiceTest {

	private static final long USER_ID = 1L;

	@Mock
	private UserRepository userRepository;

	@Mock
	private UserSettingsRepository userSettingsRepository;

	@Mock
	private BudgetRepository budgetRepository;

	@InjectMocks
	private UserSettingsService userSettingsService;

	private User user;
	private UserSettings settings;

	@BeforeEach
	void setUp() {
		user = User.create("qwer@qwer.com", "encoded-password", "김예린");
		ReflectionTestUtils.setField(user, "id", USER_ID);
		settings = UserSettings.create(user);
	}

	@Test
	void 예산_기준일을_조회한다() {
		settings.updateBudgetAnchorDay(25);
		givenActiveUserAndSettings();

		BudgetSettingsResponse response = userSettingsService.getBudgetSettings(USER_ID);

		assertThat(response.budgetAnchorDay()).isEqualTo(25);
	}

	@Test
	void 예산이_없으면_기준일을_저장한다() {
		givenActiveUserAndSettings();
		given(budgetRepository.existsByUserId(USER_ID)).willReturn(false);

		BudgetSettingsResponse response = userSettingsService.updateBudgetSettings(
				USER_ID, new BudgetSettingsUpdateRequest(25));

		assertThat(response.budgetAnchorDay()).isEqualTo(25);
		assertThat(settings.getBudgetAnchorDay()).isEqualTo(25);
	}

	@Test
	void 예산이_있으면_기준일_변경을_거절한다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(budgetRepository.existsByUserId(USER_ID)).willReturn(true);

		assertThatThrownBy(() -> userSettingsService.updateBudgetSettings(
				USER_ID, new BudgetSettingsUpdateRequest(25)))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(UserErrorCode.BUDGET_ANCHOR_LOCKED));
		assertThat(settings.getBudgetAnchorDay()).isEqualTo(1);
	}

	@Test
	void 이체_설정을_조회한다() {
		settings.updateTransferSettings(true, 1_000_000L, 2_000_000L);
		givenActiveUserAndSettings();

		TransferSettingsResponse response = userSettingsService.getTransferSettings(USER_ID);

		assertThat(response)
				.extracting("transferConsent", "transferLimitOnce", "transferLimitDaily")
				.containsExactly(true, 1_000_000L, 2_000_000L);
	}

	@Test
	void 알림_설정을_조회한다() {
		settings.updateNotificationSettings(
				true, false, true, false, LocalTime.of(23, 0), LocalTime.of(8, 0));
		givenActiveUserAndSettings();

		NotificationSettingsResponse response = userSettingsService.getNotificationSettings(USER_ID);

		assertThat(response.notiCoaching()).isTrue();
		assertThat(response.notiBudgetAlert()).isFalse();
		assertThat(response.notiTransfer()).isTrue();
		assertThat(response.notiCleanup()).isFalse();
		assertThat(response.quietHoursStart()).isEqualTo(LocalTime.of(23, 0));
		assertThat(response.quietHoursEnd()).isEqualTo(LocalTime.of(8, 0));
	}

	@Test
	void 코치_말투를_조회한다() {
		settings.updateCoachPersona(CoachPersona.DODO);
		givenActiveUserAndSettings();

		CoachPersonaResponse response = userSettingsService.getCoachPersona(USER_ID);

		assertThat(response.coachPersona()).isEqualTo(CoachPersona.DODO);
	}

	@Test
	void 이체_설정을_변경한다() {
		givenActiveUserAndSettings();

		TransferSettingsResponse response = userSettingsService.updateTransferSettings(
				USER_ID, new TransferSettingsUpdateRequest(true, 1_000_000L, 2_000_000L));

		assertThat(response.transferConsent()).isTrue();
		assertThat(settings.getTransferLimitOnce()).isEqualTo(1_000_000L);
		assertThat(settings.getTransferLimitDaily()).isEqualTo(2_000_000L);
	}

	@Test
	void 알림_설정을_변경한다() {
		givenActiveUserAndSettings();
		NotificationSettingsUpdateRequest request = new NotificationSettingsUpdateRequest(
				true, false, true, false, LocalTime.of(23, 0), LocalTime.of(8, 0));

		userSettingsService.updateNotificationSettings(USER_ID, request);

		assertThat(settings.isNotiCoaching()).isTrue();
		assertThat(settings.isNotiBudgetAlert()).isFalse();
		assertThat(settings.getQuietHoursStart()).isEqualTo(LocalTime.of(23, 0));
		assertThat(settings.getQuietHoursEnd()).isEqualTo(LocalTime.of(8, 0));
	}

	@Test
	void 코치_말투를_변경한다() {
		givenActiveUserAndSettings();

		userSettingsService.updateCoachPersona(
				USER_ID, new CoachPersonaUpdateRequest(CoachPersona.DODO));

		assertThat(settings.getCoachPersona()).isEqualTo(CoachPersona.DODO);
	}

	@Test
	void 활성_사용자가_아니면_설정을_변경할_수_없다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.empty());

		assertThatThrownBy(() -> userSettingsService.updateCoachPersona(
				USER_ID, new CoachPersonaUpdateRequest(CoachPersona.DODO)))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode()).isEqualTo(UserErrorCode.USER_NOT_FOUND));
		verifyNoInteractions(userSettingsRepository);
	}

	@Test
	void 사용자_설정이_없으면_오류를_반환한다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(userSettingsRepository.findById(USER_ID)).willReturn(Optional.empty());

		assertThatThrownBy(() -> userSettingsService.getTransferSettings(USER_ID))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(UserErrorCode.USER_SETTINGS_NOT_FOUND));
	}

	@Test
	void 일일_한도가_일회_한도보다_작으면_변경할_수_없다() {
		givenActiveUserAndSettings();

		assertThatThrownBy(() -> userSettingsService.updateTransferSettings(
				USER_ID, new TransferSettingsUpdateRequest(true, 1_000_000L, 500_000L)))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(UserErrorCode.INVALID_TRANSFER_LIMIT));
	}

	private void givenActiveUserAndSettings() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(userSettingsRepository.findById(USER_ID)).willReturn(Optional.of(settings));
	}
}
