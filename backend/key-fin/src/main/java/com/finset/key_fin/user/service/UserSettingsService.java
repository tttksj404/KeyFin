package com.finset.key_fin.user.service;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.budget.repository.BudgetRepository;
import com.finset.key_fin.user.dto.request.BudgetSettingsUpdateRequest;
import com.finset.key_fin.user.dto.request.CoachPersonaUpdateRequest;
import com.finset.key_fin.user.dto.request.NotificationSettingsUpdateRequest;
import com.finset.key_fin.user.dto.request.TransferSettingsUpdateRequest;
import com.finset.key_fin.user.dto.response.BudgetSettingsResponse;
import com.finset.key_fin.user.dto.response.CoachPersonaResponse;
import com.finset.key_fin.user.dto.response.NotificationSettingsResponse;
import com.finset.key_fin.user.dto.response.TransferSettingsResponse;
import com.finset.key_fin.user.entity.UserSettings;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import com.finset.key_fin.user.repository.UserSettingsRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class UserSettingsService {

	private final UserRepository userRepository;
	private final UserSettingsRepository userSettingsRepository;
	private final BudgetRepository budgetRepository;

	@Transactional(readOnly = true)
	public TransferSettingsResponse getTransferSettings(long userId) {
		validateActiveUser(userId);
		return TransferSettingsResponse.from(findSettings(userId));
	}

	@Transactional(readOnly = true)
	public NotificationSettingsResponse getNotificationSettings(long userId) {
		validateActiveUser(userId);
		return NotificationSettingsResponse.from(findSettings(userId));
	}

	@Transactional(readOnly = true)
	public CoachPersonaResponse getCoachPersona(long userId) {
		validateActiveUser(userId);
		return CoachPersonaResponse.from(findSettings(userId));
	}

	@Transactional
	public TransferSettingsResponse updateTransferSettings(
			long userId,
			TransferSettingsUpdateRequest request
	) {
		validateActiveUser(userId);
		UserSettings settings = findSettings(userId);
		settings.updateTransferSettings(
				request.transferConsent(),
				request.transferLimitOnce(),
				request.transferLimitDaily()
		);
		return TransferSettingsResponse.from(settings);
	}

	@Transactional
	public void updateNotificationSettings(long userId, NotificationSettingsUpdateRequest request) {
		validateActiveUser(userId);
		UserSettings settings = findSettings(userId);
		settings.updateNotificationSettings(
				request.notiCoaching(),
				request.notiBudgetAlert(),
				request.notiTransfer(),
				request.notiCleanup(),
				request.quietHoursStart(),
				request.quietHoursEnd()
		);
	}

	@Transactional(readOnly = true)
	public BudgetSettingsResponse getBudgetSettings(long userId) {
		validateActiveUser(userId);
		return BudgetSettingsResponse.from(findSettings(userId));
	}

	/** 기준일은 예산 주기·잔액·알림의 기준이라 예산이 생긴 뒤에는 바꾸지 않는다. */
	@Transactional
	public BudgetSettingsResponse updateBudgetSettings(long userId, BudgetSettingsUpdateRequest request) {
		validateActiveUser(userId);
		if (budgetRepository.existsByUserId(userId)) {
			throw new BusinessException(UserErrorCode.BUDGET_ANCHOR_LOCKED);
		}
		UserSettings settings = findSettings(userId);
		settings.updateBudgetAnchorDay(request.budgetAnchorDay());
		return BudgetSettingsResponse.from(settings);
	}

	@Transactional
	public void updateCoachPersona(long userId, CoachPersonaUpdateRequest request) {
		validateActiveUser(userId);
		findSettings(userId).updateCoachPersona(request.coachPersona());
	}

	private UserSettings findSettings(long userId) {
		return userSettingsRepository.findById(userId)
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_SETTINGS_NOT_FOUND));
	}

	private void validateActiveUser(long userId) {
		userRepository.findByIdAndDeletedAtIsNull(userId)
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_NOT_FOUND));
	}
}
