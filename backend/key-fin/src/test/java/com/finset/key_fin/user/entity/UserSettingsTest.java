package com.finset.key_fin.user.entity;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.user.exception.UserErrorCode;
import org.junit.jupiter.api.Test;

import java.time.LocalTime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class UserSettingsTest {

	@Test
	void defaultsBudgetAnchorDayToFirstDay() {
		User user = User.create("kim@ssafy.io", "encoded-password", "김싸피");

		UserSettings settings = UserSettings.create(user);

		assertThat(settings.getBudgetAnchorDay()).isEqualTo(1);
		assertThat(settings.isTransferConsent()).isFalse();
		assertThat(settings.getTransferLimitOnce()).isNull();
		assertThat(settings.getTransferLimitDaily()).isNull();
		assertThat(settings.getCoachPersona()).isEqualTo(CoachPersona.PLAIN);
	}

	@Test
	void updatesBudgetAnchorDayWithinRange() {
		UserSettings settings = UserSettings.create(
				User.create("kim@ssafy.io", "encoded-password", "김싸피"));

		settings.updateBudgetAnchorDay(25);

		assertThat(settings.getBudgetAnchorDay()).isEqualTo(25);
	}

	@Test
	void rejectsBudgetAnchorDayOutsideRange() {
		UserSettings settings = UserSettings.create(
				User.create("kim@ssafy.io", "encoded-password", "김싸피"));

		for (int day : new int[]{0, 29}) {
			assertThatThrownBy(() -> settings.updateBudgetAnchorDay(day))
					.isInstanceOfSatisfying(BusinessException.class,
							exception -> assertThat(exception.getErrorCode())
									.isEqualTo(UserErrorCode.INVALID_BUDGET_ANCHOR_DAY));
		}
		assertThat(settings.getBudgetAnchorDay()).isEqualTo(1);
	}

	@Test
	void updatesTransferSettings() {
		UserSettings settings = UserSettings.create(
				User.create("kim@ssafy.io", "encoded-password", "김싸피"));

		settings.updateTransferSettings(true, 1_000_000L, 2_000_000L);

		assertThat(settings.isTransferConsent()).isTrue();
		assertThat(settings.getTransferLimitOnce()).isEqualTo(1_000_000L);
		assertThat(settings.getTransferLimitDaily()).isEqualTo(2_000_000L);
	}

	@Test
	void allowsUnsetTransferLimits() {
		UserSettings settings = UserSettings.create(
				User.create("kim@ssafy.io", "encoded-password", "김싸피"));

		settings.updateTransferSettings(true, null, null);

		assertThat(settings.isTransferConsent()).isTrue();
		assertThat(settings.getTransferLimitOnce()).isNull();
		assertThat(settings.getTransferLimitDaily()).isNull();
	}

	@Test
	void rejectsNonPositiveTransferLimit() {
		UserSettings settings = UserSettings.create(
				User.create("kim@ssafy.io", "encoded-password", "김싸피"));

		assertThatThrownBy(() -> settings.updateTransferSettings(true, 0L, null))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(UserErrorCode.INVALID_TRANSFER_LIMIT));
	}

	@Test
	void rejectsDailyLimitSmallerThanOneTimeLimit() {
		UserSettings settings = UserSettings.create(
				User.create("kim@ssafy.io", "encoded-password", "김싸피"));

		assertThatThrownBy(() -> settings.updateTransferSettings(true, 1_000_000L, 500_000L))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(UserErrorCode.INVALID_TRANSFER_LIMIT));
	}

	@Test
	void 코치_말투를_변경한다() {
		UserSettings settings = UserSettings.create(
				User.create("kim@ssafy.io", "encoded-password", "김싸피"));

		settings.updateCoachPersona(CoachPersona.DODO);

		assertThat(settings.getCoachPersona()).isEqualTo(CoachPersona.DODO);
	}

	@Test
	void 알림과_방해금지_설정을_변경한다() {
		UserSettings settings = UserSettings.create(
				User.create("kim@ssafy.io", "encoded-password", "김싸피"));

		settings.updateNotificationSettings(
				true, false, true, false,
				LocalTime.of(23, 0), LocalTime.of(8, 0));

		assertThat(settings.isNotiCoaching()).isTrue();
		assertThat(settings.isNotiBudgetAlert()).isFalse();
		assertThat(settings.isNotiTransfer()).isTrue();
		assertThat(settings.isNotiCleanup()).isFalse();
		assertThat(settings.getQuietHoursStart()).isEqualTo(LocalTime.of(23, 0));
		assertThat(settings.getQuietHoursEnd()).isEqualTo(LocalTime.of(8, 0));
	}

	@Test
	void 방해금지_시각을_모두_null로_설정하면_해제한다() {
		UserSettings settings = UserSettings.create(
				User.create("kim@ssafy.io", "encoded-password", "김싸피"));
		settings.updateNotificationSettings(
				true, true, true, true,
				LocalTime.of(23, 0), LocalTime.of(8, 0));

		settings.updateNotificationSettings(true, true, true, true, null, null);

		assertThat(settings.getQuietHoursStart()).isNull();
		assertThat(settings.getQuietHoursEnd()).isNull();
	}

	@Test
	void 방해금지_시각을_하나만_입력하면_거절한다() {
		UserSettings settings = UserSettings.create(
				User.create("kim@ssafy.io", "encoded-password", "김싸피"));

		assertThatThrownBy(() -> settings.updateNotificationSettings(
				true, true, true, true, LocalTime.of(23, 0), null))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(UserErrorCode.INVALID_QUIET_HOURS));
	}

	@Test
	void 방해금지_시작과_종료가_같으면_거절한다() {
		UserSettings settings = UserSettings.create(
				User.create("kim@ssafy.io", "encoded-password", "김싸피"));

		assertThatThrownBy(() -> settings.updateNotificationSettings(
				true, true, true, true, LocalTime.of(23, 0), LocalTime.of(23, 0)))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(UserErrorCode.INVALID_QUIET_HOURS));
	}
}
