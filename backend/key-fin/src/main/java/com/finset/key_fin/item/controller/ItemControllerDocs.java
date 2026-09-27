package com.finset.key_fin.item.controller;

import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.item.dto.request.ItemEquipmentUpdateRequest;
import com.finset.key_fin.item.dto.response.AvatarEquipmentResponse;
import com.finset.key_fin.item.dto.response.UserItemResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.ExampleObject;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.parameters.RequestBody;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Positive;

import java.util.List;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

@Tag(name = "아이템", description = "내 보유 아바타 아이템 조회 및 장착·해제")
@SecurityRequirement(name = "bearerAuth")
@ApiResponses({
		@ApiResponse(responseCode = "400", description = "잘못된 slotType 또는 userItemId (COMMON_001)",
				content = @Content(schema = @Schema(implementation = BaseResponse.class))),
		@ApiResponse(responseCode = "401", description = "Access Token이 없거나 유효하지 않음",
				content = @Content(schema = @Schema(implementation = BaseResponse.class))),
		@ApiResponse(responseCode = "404", description = "활성 사용자 없음 (USER_001) 또는 보유 아이템 없음 (ITEM_001)",
				content = @Content(schema = @Schema(implementation = BaseResponse.class))),
		@ApiResponse(responseCode = "500", description = "서버 내부 오류",
				content = @Content(schema = @Schema(implementation = BaseResponse.class)))
})
public interface ItemControllerDocs {
	@Operation(summary = "보유 아이템 조회",
			description = "본인 소유 아이템을 보유 내역 ID 오름차순으로 반환합니다. slotType 생략 시 전체 조회합니다. "
					+ "기본 에셋은 포함하지 않으며 비활성 상품도 이미 보유했다면 포함합니다. 결과가 없으면 빈 배열입니다.")
	@ApiResponse(responseCode = "200", description = "조회 성공", useReturnTypeSchema = true,
			content = @Content(mediaType = APPLICATION_JSON_VALUE, examples = @ExampleObject(value = """
					{"success":true,"code":"SUCCESS","message":"요청이 성공했습니다.",
					 "data":[{"userItemId":101,"itemId":3,"name":"파란 셔츠",
					 "slotType":"UPPER_BODY","assetKey":"shirt_blue","equipped":true}]}
					""")))
	BaseResponse<List<UserItemResponse>> getItems(
			@Parameter(hidden = true) Long userId,
			@Parameter(description = "조회할 아바타 부위. 빈 값은 허용하지 않음",
					schema = @Schema(type = "string", allowableValues = {
							"HEAD", "FACE", "UPPER_BODY", "LOWER_BODY", "SOCKS", "FOOTWEAR"}))
			String slotType
	);

	@Operation(summary = "아이템 장착 상태 변경",
			description = "equipped가 true이면 장착·교체하고 false이면 해당 아이템만 해제합니다. "
					+ "부위는 서버가 판단하며 같은 부위의 기존 아이템은 자동 해제합니다. 보유 레코드는 유지합니다. "
					+ "같은 상태를 반복 요청해도 성공하며 변경 후 전체 착장을 부위 순서로 반환합니다. "
					+ "모든 부위가 해제 가능하며 목록에 없는 부위는 모바일에서 기본 에셋을 표시합니다.")
	@ApiResponse(responseCode = "200", description = "변경 후 전체 착장", useReturnTypeSchema = true,
			content = @Content(mediaType = APPLICATION_JSON_VALUE, examples = {
					@ExampleObject(name = "장착 후 착장", value = """
							{"success":true,"code":"SUCCESS","message":"요청이 성공했습니다.",
							 "data":{"equipped":[{"userItemId":101,"itemId":3,"slotType":"UPPER_BODY","assetKey":"shirt_blue"}]}}
							"""),
					@ExampleObject(name = "모두 해제한 착장", value = """
							{"success":true,"code":"SUCCESS","message":"요청이 성공했습니다.","data":{"equipped":[]}}
							""")
			}))
	@ApiResponse(responseCode = "400",
			description = "잘못된 userItemId 또는 equipped 누락·null (COMMON_001), 본문 누락 또는 잘못된 JSON (COMMON_002)",
			content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	BaseResponse<AvatarEquipmentResponse> updateEquipment(
			@Parameter(hidden = true) Long userId,
			@Parameter(description = "UserItem의 ID. 상품 ID가 아님",
					schema = @Schema(type = "integer", format = "int64", minimum = "1"))
			@Positive long userItemId,
			@RequestBody(required = true, content = @Content(mediaType = APPLICATION_JSON_VALUE,
					schema = @Schema(implementation = ItemEquipmentUpdateRequest.class), examples = {
							@ExampleObject(name = "장착·교체", value = "{\"equipped\":true}"),
							@ExampleObject(name = "해제", value = "{\"equipped\":false}")
					}))
			@Valid ItemEquipmentUpdateRequest request
	);
}
