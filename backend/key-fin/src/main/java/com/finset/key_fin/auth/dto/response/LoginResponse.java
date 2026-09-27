package com.finset.key_fin.auth.dto.response;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "로그인 결과")
public record LoginResponse(
		@Schema(description = "API 인증에 사용하는 Access Token", example = "eyJhbGciOiJIUzI1NiJ9...")
		String accessToken,
		@Schema(description = "Access Token 재발급에 사용하는 Refresh Token", example = "eyJhbGciOiJIUzI1NiJ9...")
		String refreshToken,
		@Schema(description = "로그인 사용자 요약 정보")
		UserSummary user
) {

	@Schema(description = "로그인 사용자 요약 정보")
	public record UserSummary(
			@Schema(description = "사용자 ID", example = "1") Long id,
			@Schema(description = "사용자 이름", example = "김예린") String name
	) {
	}
}
