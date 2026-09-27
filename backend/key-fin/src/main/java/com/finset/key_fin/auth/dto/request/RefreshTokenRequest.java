package com.finset.key_fin.auth.dto.request;

import jakarta.validation.constraints.NotBlank;
import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "토큰 재발급 요청")
public record RefreshTokenRequest(
		@Schema(description = "로그인에서 발급받은 Refresh Token", example = "eyJhbGciOiJIUzI1NiJ9...")
		@NotBlank
		String refreshToken
) {
}
