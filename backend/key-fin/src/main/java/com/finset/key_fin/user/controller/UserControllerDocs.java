package com.finset.key_fin.user.controller;

import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.user.dto.request.AccountDeletionRequest;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;

@Tag(name = "사용자", description = "사용자 프로필 및 계정 관리 API입니다. Access Token이 필요합니다.")
public interface UserControllerDocs {

	@Operation(
			summary = "회원 탈퇴",
			description = "현재 비밀번호를 확인한 후 계정을 소프트 삭제하고 저장된 Refresh Token을 삭제합니다. "
					+ "탈퇴한 이메일로는 다시 가입할 수 없습니다.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(responseCode = "204", description = "회원 탈퇴 성공"),
			@ApiResponse(responseCode = "400", description = "비밀번호 누락 또는 요청 형식이 올바르지 않음 (COMMON_001)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "401", description = "Access Token 오류 또는 현재 비밀번호 불일치 (USER_007)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "403", description = "접근 권한 없음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "404", description = "활성 사용자를 찾을 수 없음 (USER_001)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "500", description = "서버 내부 오류",
					content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	})
	ResponseEntity<Void> deleteAccount(
			@Parameter(hidden = true) Long userId,
			AccountDeletionRequest request
	);
}
