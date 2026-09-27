package com.finset.key_fin.user.dto.response;

import com.finset.key_fin.user.entity.CoachPersona;
import com.finset.key_fin.user.entity.UserSettings;
import io.swagger.v3.oas.annotations.media.Schema;

public record CoachPersonaResponse(
		@Schema(description = "현재 선택한 코치 말투", example = "DODO")
		CoachPersona coachPersona
) {
	public static CoachPersonaResponse from(UserSettings settings) {
		return new CoachPersonaResponse(settings.getCoachPersona());
	}
}
