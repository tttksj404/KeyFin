package com.finset.key_fin.user.dto.response;

import com.finset.key_fin.user.entity.EmploymentStatus;
import com.finset.key_fin.user.entity.UserProfile;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.LocalDate;

public record ProfileResponse(
		@Schema(description = "생년월일", example = "2001-03-14", nullable = true)
		LocalDate birthDate,
		@Schema(description = "시·군·구 행정코드", example = "11680", nullable = true)
		String regionCode,
		@Schema(description = "고용 상태", example = "EMPLOYED", nullable = true)
		EmploymentStatus employmentStatus,
		@Schema(description = "소득 구간 코드", example = "2400_3600", nullable = true)
		String incomeBand
) {
	public static ProfileResponse from(UserProfile profile) {
		return new ProfileResponse(
				profile.getBirthDate(),
				profile.getRegionCode(),
				profile.getEmploymentStatus(),
				profile.getIncomeBand()
		);
	}
}
