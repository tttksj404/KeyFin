package com.finset.key_fin.notification.controller;

import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.notification.dto.request.PushDeviceRequest;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;

@Tag(name = "푸시 기기", description = "현재 사용자의 Android 앱 설치 등록·해제")
@SecurityRequirement(name = "bearerAuth")
public interface PushDeviceControllerDocs {
	@Operation(summary = "푸시 기기 등록·갱신", description = "설치 UUID의 사용자와 FCM 토큰을 갱신합니다. 같은 설치는 재사용하고 같은 토큰의 이전 연결은 해제합니다.")
	@ApiResponses({
			@ApiResponse(responseCode = "200", description = "등록·갱신 성공. data=null", useReturnTypeSchema = true),
			@ApiResponse(responseCode = "400", description = "UUID·토큰·플랫폼 입력 오류 (COMMON_001/002)"),
			@ApiResponse(responseCode = "401", description = "인증 필요"),
			@ApiResponse(responseCode = "404", description = "활성 사용자가 없음 (USER_001)"),
			@ApiResponse(responseCode = "409", description = "동시 변경 충돌. 재시도 가능 (PUSH_001)")
	})
	BaseResponse<Void> register(@Parameter(hidden = true) Long userId,
			@Parameter(description = "앱 설치 UUID") String installationId, PushDeviceRequest request);

	@Operation(summary = "푸시 기기 연결 해제", description = "본인 소유 설치만 비활성화하고 토큰을 비웁니다. 다른 계정 소유이거나 이미 해제된 설치에도 성공을 반환합니다.")
	@ApiResponses({
			@ApiResponse(responseCode = "200", description = "해제 처리 완료. data=null", useReturnTypeSchema = true),
			@ApiResponse(responseCode = "400", description = "UUID 형식 오류 (COMMON_001)"),
			@ApiResponse(responseCode = "401", description = "인증 필요"),
			@ApiResponse(responseCode = "409", description = "동시 변경 충돌 (PUSH_001)")
	})
	BaseResponse<Void> disconnect(@Parameter(hidden = true) Long userId, String installationId);
}
