package com.finset.key_fin.user.service;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.user.dto.request.ProfileUpdateRequest;
import com.finset.key_fin.user.entity.EmploymentStatus;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.entity.UserProfile;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserProfileRepository;
import com.finset.key_fin.user.repository.UserRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDate;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class ProfileServiceTest {

	private static final long USER_ID = 1L;

	@Mock
	private UserRepository userRepository;
	@Mock
	private UserProfileRepository userProfileRepository;
	@InjectMocks
	private ProfileService profileService;

	@Test
	void 프로필을_입력하고_저장된_값을_반환한다() {
		User user = User.create("qwer@qwer.com", "password", "김예린");
		UserProfile profile = UserProfile.create(user);
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(userProfileRepository.findById(USER_ID)).willReturn(Optional.of(profile));
		ProfileUpdateRequest request = new ProfileUpdateRequest(
				LocalDate.of(2001, 3, 14), "11680", EmploymentStatus.EMPLOYED, "2400_3600");

		var response = profileService.updateProfile(USER_ID, request);

		assertThat(response)
				.extracting("birthDate", "regionCode", "employmentStatus", "incomeBand")
				.containsExactly(
						LocalDate.of(2001, 3, 14), "11680", EmploymentStatus.EMPLOYED, "2400_3600");
	}

	@Test
	void 활성_사용자가_없으면_프로필을_수정하지_않는다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.empty());

		assertThatThrownBy(() -> profileService.updateProfile(
				USER_ID, new ProfileUpdateRequest(null, null, null, null)))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode()).isEqualTo(UserErrorCode.USER_NOT_FOUND));
		verifyNoInteractions(userProfileRepository);
	}
}
