package com.finset.key_fin.auth.dto.request;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "로그인 요청")
public record LoginRequest(
		@Schema(description = "로그인 이메일", example = "qwer@qwer.com", maxLength = 100)
		@NotBlank
		@Email
		@Size(max = 100)
		String email,

		@Schema(description = "비밀번호", example = "qwer1234@", format = "password")
		@NotBlank
		String password
) {
}
