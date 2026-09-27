package com.finset.key_fin.auth.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

@Schema(description = "회원가입 요청")
public record SignupRequest(
		@Schema(description = "가입 이메일", example = "qwer@qwer.com", maxLength = 100)
		@NotBlank
		@Email
		@Size(max = 100)
		String email,

		@Schema(description = "비밀번호", example = "qwer1234@", format = "password")
		@NotBlank
		String password,

		@Schema(description = "사용자 이름", example = "김예린", maxLength = 30)
		@NotBlank
		@Size(max = 30)
		String name
) {
}
