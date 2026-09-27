package com.finset.key_fin.notification.controller;

import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.notification.dto.response.NotificationListResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.ExampleObject;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;

@Tag(name = "알림함", description = "로그인한 사용자의 알림 목록 조회와 개별 읽음 처리")
@SecurityRequirement(name = "bearerAuth")
public interface NotificationControllerDocs {
	@Operation(summary = "알림 목록 조회", description = "본인 알림을 ID 내림차순으로 조회합니다. "
			+ "unreadOnly=true이면 미읽음만 조회합니다. cursor에는 직전 응답의 nextCursor를 전달합니다. "
			+ "nextCursor=null이면 마지막 페이지입니다. createdAt은 Asia/Seoul 기준이며 조회만으로 읽음 처리하지 않습니다.")
	@ApiResponses({
			@ApiResponse(responseCode = "200", description = "조회 성공", useReturnTypeSchema = true,
					content = @Content(mediaType = "application/json", examples = @ExampleObject(value = """
							{"success":true,"code":"SUCCESS","message":"요청이 성공했습니다.","data":{
							"items":[{"id":123,"type":"TRANSFER_REQUEST","title":"이체 승인 요청",
							"body":"확인이 필요한 이체 요청이 있습니다.","refId":"456","requiresAction":true,
							"isRead":false,"createdAt":"2026-09-16T22:00:00"}],"nextCursor":null}}
							"""))),
			@ApiResponse(responseCode = "400", description = "목록 파라미터 입력 오류 (COMMON_001)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "401", description = "Access Token이 없거나 유효하지 않음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	})
	BaseResponse<NotificationListResponse> list(
			@Parameter(hidden = true) Long userId,
			@Parameter(description = "true: 미읽음만, false: 전체", schema = @Schema(defaultValue = "false")) boolean unreadOnly,
			@Parameter(description = "직전 응답의 nextCursor. 생략하면 첫 페이지", schema = @Schema(minimum = "1")) Long cursor,
			@Parameter(description = "페이지 크기", schema = @Schema(minimum = "1", maximum = "100", defaultValue = "20")) Integer size);

	@Operation(summary = "알림 읽음 처리", description = "요청 본문 없이 본인 알림을 읽음 처리합니다. 이미 읽은 알림도 성공합니다. "
			+ "다른 사용자 알림과 존재하지 않는 알림은 동일한 404를 반환합니다. 이체 승인과 조치 필요 여부는 변경하지 않습니다.")
	@ApiResponses({
			@ApiResponse(responseCode = "200", description = "읽음 처리 성공. data=null", useReturnTypeSchema = true,
					content = @Content(mediaType = "application/json", examples = @ExampleObject(value = """
							{"success":true,"code":"SUCCESS","message":"요청이 성공했습니다.","data":null}
							"""))),
			@ApiResponse(responseCode = "400", description = "알림 ID 입력 오류 (COMMON_001)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "401", description = "Access Token이 없거나 유효하지 않음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "404", description = "본인 소유 알림을 찾을 수 없음 (NOTI_001)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	})
	BaseResponse<Void> markRead(@Parameter(hidden = true) Long userId,
			@Parameter(description = "읽음 처리할 알림 ID", schema = @Schema(minimum = "1")) long notificationId);
}
