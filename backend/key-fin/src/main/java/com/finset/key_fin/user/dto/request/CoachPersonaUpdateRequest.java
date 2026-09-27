package com.finset.key_fin.user.dto.request;

import com.finset.key_fin.user.entity.CoachPersona;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotNull;

public record CoachPersonaUpdateRequest(
		@Schema(
				description = "코치 말투 코드",
				example = "DODO",
				allowableValues = {"PLAIN", "DODO", "ONSOON", "JIBANG"},
				requiredMode = Schema.RequiredMode.REQUIRED
		)
		@NotNull(message = "코치 말투는 필수입니다.")
		CoachPersona coachPersona
) {
}
