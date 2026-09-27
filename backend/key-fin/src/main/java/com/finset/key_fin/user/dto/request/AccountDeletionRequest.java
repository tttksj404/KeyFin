package com.finset.key_fin.user.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

public record AccountDeletionRequest(
		@Schema(description = "현재 비밀번호", example = "qwer1234@", requiredMode = Schema.RequiredMode.REQUIRED)
		@NotBlank(message = "현재 비밀번호는 필수입니다.")
		String password
) {
}
