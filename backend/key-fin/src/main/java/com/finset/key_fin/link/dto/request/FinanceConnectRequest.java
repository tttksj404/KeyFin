package com.finset.key_fin.link.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record FinanceConnectRequest(
		@NotBlank(message = "금융망 가입 이메일은 필수입니다.")
		@Email(message = "올바른 이메일 형식이어야 합니다.")
		@Size(max = 100, message = "이메일은 100자를 초과할 수 없습니다.")
		@Schema(description = "금융망 가입 이메일", example = "finance@qwer.com")
		String financeEmail
) {
}
