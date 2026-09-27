package com.finset.key_fin.room.controller;

import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.room.dto.response.RoomResponse;
import com.finset.key_fin.room.dto.response.StickerRemovalResponse;
import com.finset.key_fin.room.dto.request.StickerRemovalRequest;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.ExampleObject;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

@Tag(
		name = "방",
		description = "방 초기 화면에 필요한 아바타, 가구, 코인과 출석 데이터를 제공합니다."
)
public interface RoomControllerDocs {

	@Operation(
			summary = "방 홈 화면 데이터 조회",
			description = "인증된 사용자의 방 초기 화면 데이터를 조회합니다. avatar.equipped는 실제 장착 상태이며 "
					+ "미장착 부위는 모바일에서 기본 에셋을 표시합니다. furnitures는 실제 설치된 가구를 보유 가구 ID "
					+ "오름차순으로 반환하며 미설치 가구는 제외합니다. 코인은 최신 원장의 잔액이며 원장이 없으면 0입니다. "
					+ "출석은 한국 시간 기준 오늘 ATTEND 원장의 존재 여부이며, 조회 시 출석 보상을 지급하지 않습니다. "
					+ "overEnvelopes는 현재 확정 예산에서 지출이 예산액보다 큰 봉투 ID 목록입니다. 예산 미생성·미확정이면 빈 목록이며 예산을 생성하지 않습니다. "
					+ "환불·재분류·주기 변경은 최신 집계에 반영되며, 지출과 예산이 같으면 초과가 아닙니다. 모바일은 1번 식탁과 4번 커피테이블에 효과를 표시합니다. "
					+ "전체 예산 초과 처리 시 설치된 모든 바닥 가구에 딱지를 붙입니다. 초과 상태가 계속되는 동안에는 직접 제거한 딱지를 다시 붙이거나 추가 설치한 가구에 새로 붙이지 않습니다. "
					+ "결제 취소·환불·재분류로 현재 확정 예산의 총지출이 예산 이하가 되면 보관 가구를 포함한 모든 딱지를 자동 제거합니다. 복구 후 다시 초과하면 같은 예산 기간이라도 그때 설치된 모든 바닥 가구에 다시 붙입니다. "
					+ "stickers.total은 현재 설치된 바닥 가구 수, count는 그중 딱지가 붙은 수입니다. 보관한 일반 가구의 딱지는 유지되지만 집계에서 제외합니다. "
					+ "필수 가구는 단독 해제할 수 없으며 일괄 배치 저장으로 같은 종류의 구매 가구와 교체할 수 있습니다. avatar.reaction은 현재 null입니다.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(
					responseCode = "200",
					description = "방 홈 화면 데이터 조회 성공",
					useReturnTypeSchema = true,
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							examples = @ExampleObject(
									name = "방 조회 성공",
									description = "가구 목록은 축약했으며 바닥 가구 7개가 설치된 예시입니다.",
									value = """
											{"success":true,"code":"SUCCESS","message":"요청이 성공했습니다.","data":{
											 "avatar":{"equipped":[{"userItemId":101,"slotType":"HEAD","itemId":1,"assetKey":"hat_blue"}],"reaction":null},
											 "furnitures":[{"userFurnitureId":201,"itemId":4,"slotType":"FLOOR","assetKey":"sofa_default",
											 "placementStatus":"FLOOR","placementDirection":"FRONT_RIGHT","positionX":164.875,"positionY":226.000,"layer":0,
											 "defaultFurnitureType":"SOFA","furnitureType":"SOFA","stickerAttached":false,"canUnplace":false}],
											 "coin":{"balance":0},"attendance":{"checkedToday":false},"stickers":{"count":0,"total":7,"removableToday":false},"overEnvelopes":[1,4]}}
											"""
							)
					)
			),
			@ApiResponse(
					responseCode = "401",
					description = "Access Token이 없거나 유효하지 않음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "404",
					description = "활성 사용자를 찾을 수 없음 (USER_001)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "500",
					description = "서버 내부 오류",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			)
	})
	BaseResponse<RoomResponse> getRoom(Long userId);

	@Operation(summary = "압류 딱지 한 개 제거",
			description = "인증 사용자 소유의 현재 바닥에 설치된 가구에서 딱지 한 개를 제거합니다. 일반 가구와 러그도 대상이며 보관 중이면 다시 설치해야 합니다. 횟수 제한 없이 연속 제거할 수 있으며 "
					+ "초과 상태가 계속되는 동안에는 재부착되지 않습니다. 예산 복구 후 재초과하거나 다음 예산 기간에 초과하면 다시 부착되며, 이 딱지도 바로 제거할 수 있습니다.",
			security = @SecurityRequirement(name = "bearerAuth"))
	@ApiResponses({
			@ApiResponse(responseCode = "200", description = "제거 성공", useReturnTypeSchema = true,
					content = @Content(mediaType = APPLICATION_JSON_VALUE, examples = @ExampleObject(value = """
							{"success":true,"code":"SUCCESS","message":"요청이 성공했습니다.","data":{
						"userFurnitureId":123,"stickerAttached":false,"stickers":{"count":6,"total":7,"removableToday":true}}}
							"""))),
			@ApiResponse(responseCode = "400", description = "입력 오류 (COMMON_001/COMMON_002), 바닥에 설치된 가구가 아님 (ROOM_001)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "401", description = "인증 실패", content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "404", description = "활성 사용자 없음 (USER_001), 보유 가구 없음 (FURNITURE_001)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "409", description = "대상 딱지 없음 또는 이미 제거됨 (ROOM_003)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "500", description = "서버 내부 오류", content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	})
	BaseResponse<StickerRemovalResponse> removeSticker(Long userId, StickerRemovalRequest request);
}
