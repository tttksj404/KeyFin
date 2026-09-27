package com.finset.key_fin.user.service;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.user.dto.request.ProfileUpdateRequest;
import com.finset.key_fin.user.dto.response.ProfileResponse;
import com.finset.key_fin.user.entity.UserProfile;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserProfileRepository;
import com.finset.key_fin.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class ProfileService {

	private final UserRepository userRepository;
	private final UserProfileRepository userProfileRepository;

	@Transactional
	public ProfileResponse updateProfile(long userId, ProfileUpdateRequest request) {
		validateActiveUser(userId);
		UserProfile profile = userProfileRepository.findById(userId)
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_PROFILE_NOT_FOUND));
		profile.update(
				request.birthDate(),
				request.regionCode(),
				request.employmentStatus(),
				request.incomeBand()
		);
		return ProfileResponse.from(profile);
	}

	private void validateActiveUser(long userId) {
		userRepository.findByIdAndDeletedAtIsNull(userId)
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_NOT_FOUND));
	}
}
