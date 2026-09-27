package com.finset.key_fin.user.controller;

import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.user.dto.request.ProfileUpdateRequest;
import com.finset.key_fin.user.dto.response.ProfileResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.ExampleObject;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

@Tag(name = "사용자", description = "사용자 프로필 및 계정 관리 API입니다. Access Token이 필요합니다.")
public interface ProfileControllerDocs {

	@Operation(
			summary = "프로필 입력",
			description = "정책 추천에 사용하는 생년월일·지역·고용 상태·소득 구간을 전체 교체합니다. "
					+ "모든 필드는 선택값이며 null이면 기존 값을 삭제합니다.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(responseCode = "200", description = "프로필 입력 성공", useReturnTypeSchema = true,
					content = @Content(mediaType = APPLICATION_JSON_VALUE,
							examples = @ExampleObject(value = """
									{"success":true,"code":"SUCCESS","message":"요청이 성공했습니다.","data":{"birthDate":"2001-03-14","regionCode":"11680","employmentStatus":"EMPLOYED","incomeBand":"2400_3600"}}
									"""))),
			@ApiResponse(responseCode = "400", description = "날짜 또는 프로필 입력 형식이 올바르지 않음 (COMMON_001)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "401", description = "Access Token이 없거나 유효하지 않거나 만료됨",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "403", description = "접근 권한 없음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "404", description = "활성 사용자 또는 프로필을 찾을 수 없음 (USER_001, USER_008)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "500", description = "서버 내부 오류",
					content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	})
	BaseResponse<ProfileResponse> updateProfile(
			@Parameter(hidden = true) Long userId,
			ProfileUpdateRequest request
	);
}
