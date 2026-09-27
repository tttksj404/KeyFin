package com.finset.key_fin.auth.dto.response;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Access Token 재발급 결과")
public record AccessTokenResponse(
		@Schema(description = "새로 발급된 Access Token", example = "eyJhbGciOiJIUzI1NiJ9...")
		String accessToken
) {
}
