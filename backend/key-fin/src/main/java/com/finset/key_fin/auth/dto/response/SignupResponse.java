package com.finset.key_fin.auth.dto.response;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "회원가입 결과")
public record SignupResponse(
		@Schema(description = "생성된 사용자 ID", example = "1")
		Long userId
) {
}
