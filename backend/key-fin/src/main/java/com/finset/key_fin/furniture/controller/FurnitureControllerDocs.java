package com.finset.key_fin.furniture.controller;

import com.finset.key_fin.furniture.dto.request.FurniturePlacementUpdateRequest;
import com.finset.key_fin.furniture.dto.request.FurniturePlacementsUpdateRequest;
import com.finset.key_fin.furniture.dto.response.UserFurnitureResponse;
import com.finset.key_fin.global.base.BaseResponse;
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

@Tag(name = "가구", description = "내 보유 가구 조회 및 설치·이동·해제")
@SecurityRequirement(name = "bearerAuth")
@ApiResponses({
		@ApiResponse(responseCode = "400", description = "잘못된 slotType 또는 userFurnitureId (COMMON_001)",
				content = @Content(schema = @Schema(implementation = BaseResponse.class))),
		@ApiResponse(responseCode = "401", description = "Access Token이 없거나 유효하지 않음",
				content = @Content(schema = @Schema(implementation = BaseResponse.class))),
		@ApiResponse(responseCode = "404", description = "활성 사용자 없음 (USER_001) 또는 보유 가구 없음 (FURNITURE_001)",
				content = @Content(schema = @Schema(implementation = BaseResponse.class))),
		@ApiResponse(responseCode = "500", description = "서버 내부 오류",
				content = @Content(schema = @Schema(implementation = BaseResponse.class)))
})
public interface FurnitureControllerDocs {
	@Operation(summary = "보유 가구 조회", description = "설치·미설치 가구를 보유 가구 ID 오름차순으로 반환합니다. "
			+ "slotType 생략 시 전체 조회하며 결과가 없으면 빈 배열입니다. 판매 중지된 상품도 이미 보유했다면 포함합니다. "
			+ "defaultFurnitureType은 기본 지급 상품 식별값, furnitureType은 색상과 무관한 필수 가구 종류(SOFA/TV/DINING_TABLE/COFFEE_TABLE, 그 외 null)입니다. "
			+ "stickerAttached는 딱지 부착 상태, canUnplace는 단독 해제 가능 여부입니다. 설치된 필수 가구는 일괄 저장으로 교체할 수 있습니다.")
	@ApiResponse(responseCode = "200", description = "조회 성공", useReturnTypeSchema = true,
			content = @Content(mediaType = APPLICATION_JSON_VALUE, examples = @ExampleObject(value = """
					{"success":true,"code":"SUCCESS","message":"요청이 성공했습니다.",
					 "data":[{"userFurnitureId":201,"itemId":4,"name":"파란 소파","slotType":"FLOOR",
					 "assetKey":"sofa_blue","placed":false,"placementStatus":null,"placementDirection":null,
					 "positionX":null,"positionY":null,"layer":0,"defaultFurnitureType":null,"furnitureType":null,"stickerAttached":false,"canUnplace":true}]}
					""")))
	BaseResponse<List<UserFurnitureResponse>> getFurnitures(
			@Parameter(hidden = true) Long userId,
			@Parameter(description = "가구의 설치 가능 유형. 빈 값은 허용하지 않음",
					schema = @Schema(type = "string", allowableValues = {"FLOOR", "WALL"})) String slotType
	);

	@Operation(summary = "가구 배치 상태 변경", description = "placed=true이면 면·방향·좌표를 모두 보내 설치하거나 현재 배치를 교체합니다. "
			+ "layer는 생략 또는 null이면 0이며 음수도 허용합니다. placed=false이면 나머지 필드는 생략 또는 null이어야 합니다. "
			+ "일반 가구 해제 시 면·방향·좌표는 null, layer는 0으로 초기화하고 보유 내역은 유지합니다. "
			+ "설치된 필수 가구는 색상에 관계없이 canUnplace=false이며 단독 해제할 수 없습니다. 같은 종류와의 교체는 PUT /furnitures/placements를 사용합니다. "
			+ "변경 후 소파·TV·식탁·커피테이블은 각각 정확히 1개여야 합니다. 이동·회전·일반 가구 보관 시 stickerAttached는 유지됩니다. "
			+ "같은 요청을 반복해도 성공하며 변경된 가구를 반환합니다. 타인 소유와 미존재 가구는 같은 오류입니다. "
			+ "좌표는 327×586 씬 기준으로 소수점 최대 3자리입니다. 겹침·격자·실제 면 내부 판정은 클라이언트가 담당합니다.")
	@ApiResponse(responseCode = "200", description = "변경된 가구", useReturnTypeSchema = true,
			content = @Content(mediaType = APPLICATION_JSON_VALUE, examples = {
					@ExampleObject(name = "설치 후", value = """
							{"success":true,"code":"SUCCESS","message":"요청이 성공했습니다.",
							 "data":{"userFurnitureId":201,"itemId":4,"name":"파란 소파","slotType":"FLOOR",
							 "assetKey":"sofa_blue","placed":true,"placementStatus":"FLOOR","placementDirection":"FRONT_RIGHT",
							 "positionX":165.000,"positionY":280.000,"layer":0,"defaultFurnitureType":null,"furnitureType":null,"stickerAttached":false,"canUnplace":true}}
							"""),
					@ExampleObject(name = "해제 후", value = """
							{"success":true,"code":"SUCCESS","message":"요청이 성공했습니다.",
							 "data":{"userFurnitureId":201,"itemId":4,"name":"파란 소파","slotType":"FLOOR",
							 "assetKey":"sofa_blue","placed":false,"placementStatus":null,"placementDirection":null,
							 "positionX":null,"positionY":null,"layer":0,"defaultFurnitureType":null,"furnitureType":null,"stickerAttached":false,"canUnplace":true}}
							""")
			}))
	@ApiResponse(responseCode = "400", description = "필수값 누락·좌표 범위/정밀도·해제 필드 오류 (COMMON_001), "
			+ "본문 누락·JSON 파싱 오류 (COMMON_002), 가구 유형과 설치 면 불일치 (FURNITURE_002)",
			content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	@ApiResponse(responseCode = "409", description = "필수 가구 단독 해제 불가 (FURNITURE_003), 필수 가구 누락·중복 (FURNITURE_004)",
			content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	BaseResponse<UserFurnitureResponse> updatePlacement(
			@Parameter(hidden = true) Long userId,
			@Parameter(description = "UserFurniture의 ID. 상품 ID가 아님",
					schema = @Schema(type = "integer", format = "int64", minimum = "1")) @Positive long userFurnitureId,
			@RequestBody(required = true, content = @Content(mediaType = APPLICATION_JSON_VALUE,
					schema = @Schema(implementation = FurniturePlacementUpdateRequest.class), examples = {
							@ExampleObject(name = "설치·이동", value = """
									{"placed":true,"placementStatus":"FLOOR","placementDirection":"FRONT_RIGHT",
									 "positionX":165.000,"positionY":280.000,"layer":0}
									"""),
							@ExampleObject(name = "해제", value = "{\"placed\":false}")
					})) @Valid FurniturePlacementUpdateRequest request
	);

	@Operation(summary = "방 가구 배치 일괄 저장", description = "완료 버튼에서 최종 설치 가구 전체를 한 번 전송합니다. 변경분만 보내면 안 됩니다. "
			+ "목록에서 빠진 가구는 보관 상태가 되며 보유 내역은 유지됩니다. 서버 보유 가구 ID가 없는 앱 전용 오브젝트는 제외하되, "
			+ "화면에서 표현하지 못하는 서버 가구는 기존 배치 정보를 유지하여 포함해야 합니다. "
			+ "최대 100개이며 ID 중복은 불가합니다. 소파·TV·식탁·커피테이블은 색상·디자인과 무관하게 각각 정확히 1개가 필수입니다. "
			+ "필수 가구는 같은 종류로 교체할 때 딱지를 이전하고 이전 가구에서는 제거합니다. 일반 가구는 보관·재설치해도 딱지를 유지합니다. "
			+ "전체 검증 후 하나의 트랜잭션으로 저장하고 실패 시 전부 취소합니다. 같은 요청의 재시도는 멱등이며 동시 요청은 마지막 저장이 반영됩니다. "
			+ "좌표는 327×586 기준으로 소수점 최대 3자리, layer는 정수만 허용하며 생략·null은 0입니다. 겹침·격자·면 내부 판정은 앱이 담당합니다.")
	@ApiResponse(responseCode = "200", description = "미설치를 포함한 전체 보유 가구를 ID 오름차순 반환", useReturnTypeSchema = true)
	@ApiResponse(responseCode = "400", description = "필수값·중복 ID·최대 100개·좌표 검증 오류 (COMMON_001), JSON 파싱 오류 (COMMON_002), 설치 면 불일치 (FURNITURE_002)",
			content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	@ApiResponse(responseCode = "409", description = "필수 가구 누락·중복, 빈 배치 (FURNITURE_004)",
			content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	BaseResponse<List<UserFurnitureResponse>> updatePlacements(
			@Parameter(hidden = true) Long userId,
			@RequestBody(required = true, content = @Content(mediaType = APPLICATION_JSON_VALUE,
					schema = @Schema(implementation = FurniturePlacementsUpdateRequest.class), examples = @ExampleObject(
							name = "최종 배치 전체", description = "ID는 본인이 보유한 냉장고·소파·TV의 ID로 대체합니다. 일반 가구도 최종 설치 목록에 포함합니다.", value = """
							{"placements":[
							 {"userFurnitureId":101,"placementStatus":"FLOOR","placementDirection":"FRONT_RIGHT","positionX":60,"positionY":430,"layer":0},
							 {"userFurnitureId":102,"placementStatus":"FLOOR","placementDirection":"FRONT_LEFT","positionX":160,"positionY":500,"layer":0},
							 {"userFurnitureId":103,"placementStatus":"FLOOR","placementDirection":"FRONT_RIGHT","positionX":260,"positionY":586,"layer":0}
							]}
							"""))) @Valid FurniturePlacementsUpdateRequest request
	);
}
