package com.finset.key_fin.user.entity;

import org.junit.jupiter.api.Test;

import java.time.LocalDate;

import static org.assertj.core.api.Assertions.assertThat;

class UserProfileTest {

	@Test
	void 프로필_선택_정보를_전체_교체한다() {
		User user = User.create("qwer@qwer.com", "password", "김예린");
		UserProfile profile = UserProfile.create(user);

		profile.update(
				LocalDate.of(2001, 3, 14),
				"11680",
				EmploymentStatus.EMPLOYED,
				"2400_3600"
		);

		assertThat(profile)
				.extracting("birthDate", "regionCode", "employmentStatus", "incomeBand")
				.containsExactly(
						LocalDate.of(2001, 3, 14),
						"11680",
						EmploymentStatus.EMPLOYED,
						"2400_3600"
				);

		profile.update(null, null, null, null);

		assertThat(profile)
				.extracting("birthDate", "regionCode", "employmentStatus", "incomeBand")
				.containsOnlyNulls();
	}
}
