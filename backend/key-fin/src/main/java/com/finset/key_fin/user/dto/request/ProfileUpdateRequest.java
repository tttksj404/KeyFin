package com.finset.key_fin.user.dto.request;

import com.finset.key_fin.user.entity.EmploymentStatus;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Past;
import jakarta.validation.constraints.Pattern;

import java.time.LocalDate;

public record ProfileUpdateRequest(
		@Schema(description = "생년월일", example = "2001-03-14", nullable = true)
		@Past(message = "생년월일은 과거 날짜여야 합니다.")
		LocalDate birthDate,

		@Schema(description = "시·군·구 행정코드", example = "11680", nullable = true)
		@Pattern(regexp = "\\d{5,10}", message = "지역 코드는 5~10자리 숫자여야 합니다.")
		String regionCode,

		@Schema(description = "고용 상태", example = "EMPLOYED", nullable = true,
				allowableValues = {"STUDENT", "JOB_SEEKER", "EMPLOYED", "FREELANCER"})
		EmploymentStatus employmentStatus,

		@Schema(description = "소득 구간 코드", example = "2400_3600", nullable = true)
		@Pattern(regexp = "[A-Z0-9_]{1,20}", message = "소득 구간 형식이 올바르지 않습니다.")
		String incomeBand
) {
}
