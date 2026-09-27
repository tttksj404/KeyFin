package com.finset.key_fin.shop.controller;

import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.shop.dto.request.ShopPurchaseRequest;
import com.finset.key_fin.shop.dto.response.ShopItemResponse;
import com.finset.key_fin.shop.dto.response.ShopPurchaseResponse;
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

import java.util.List;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

@Tag(name = "상점", description = "아바타·가구 상품 조회 및 코인 구매")
@SecurityRequirement(name = "bearerAuth")
@ApiResponses({
		@ApiResponse(responseCode = "400", description = "잘못된 입력 (COMMON_001) 또는 본문 누락·잘못된 JSON (COMMON_002)",
				content = @Content(schema = @Schema(implementation = BaseResponse.class))),
		@ApiResponse(responseCode = "401", description = "Access Token이 없거나 유효하지 않음",
				content = @Content(schema = @Schema(implementation = BaseResponse.class))),
		@ApiResponse(responseCode = "404", description = "활성 사용자 없음 (USER_001)",
				content = @Content(schema = @Schema(implementation = BaseResponse.class))),
		@ApiResponse(responseCode = "500", description = "서버 내부 오류",
				content = @Content(schema = @Schema(implementation = BaseResponse.class)))
})
public interface ShopControllerDocs {
	@Operation(summary = "상점 상품 조회", description = "판매 중인 상품을 상품 ID 오름차순으로 반환합니다. "
			+ "보유 상품도 포함하며 owned로 표시합니다. 필터 생략 시 전체, 슬롯만 지정해도 조회 가능하며 "
			+ "빈 값·알 수 없는 값·카테고리와 슬롯 불일치는 400입니다. 페이지네이션은 없고 결과가 없으면 빈 배열입니다.")
	@ApiResponse(responseCode = "200", description = "조회 성공", useReturnTypeSchema = true,
			content = @Content(mediaType = APPLICATION_JSON_VALUE, examples = @ExampleObject(value = """
					{"success":true,"code":"SUCCESS","message":"요청이 성공했습니다.","data":[
					{"itemId":123,"itemCategory":"AVATAR","slotType":"HEAD","name":"파란 모자",
					"price":100,"assetKey":"hat_blue","themeCode":null,"owned":false}]}
					""")))
	BaseResponse<List<ShopItemResponse>> getItems(
			@Parameter(hidden = true) Long userId,
			@Parameter(description = "상품 카테고리", schema = @Schema(type = "string", allowableValues = {"AVATAR", "FURNITURE"})) String itemCategory,
			@Parameter(description = "장착·배치 유형", schema = @Schema(type = "string", allowableValues = {
					"HEAD", "FACE", "UPPER_BODY", "LOWER_BODY", "SOCKS", "FOOTWEAR", "WALL", "FLOOR"})) String slotType
	);

	@Operation(summary = "상점 상품 구매", description = "상품 하나를 서버 가격으로 구매합니다. 무료 상품도 구매할 수 있습니다. "
			+ "보유 내역 생성과 코인 차감은 함께 성공하거나 함께 취소됩니다. 이미 보유한 상품의 재요청은 409이며 추가 차감하지 않습니다. "
			+ "구매 후 자동 장착·배치하지 않습니다. 해당 카테고리의 보유 내역 ID만 반환하고 나머지는 null입니다.")
	@ApiResponse(responseCode = "200", description = "구매 성공", useReturnTypeSchema = true,
			content = @Content(mediaType = APPLICATION_JSON_VALUE, examples = {
					@ExampleObject(name = "아바타 구매", value = """
							{"success":true,"code":"SUCCESS","message":"요청이 성공했습니다.","data":
							{"itemId":123,"itemCategory":"AVATAR","userItemId":501,"userFurnitureId":null,"price":100,"balance":900}}
							"""),
					@ExampleObject(name = "가구 구매", value = """
							{"success":true,"code":"SUCCESS","message":"요청이 성공했습니다.","data":
							{"itemId":124,"itemCategory":"FURNITURE","userItemId":null,"userFurnitureId":601,"price":200,"balance":700}}
							""")
			}))
	@ApiResponse(responseCode = "404", description = "활성 사용자 없음 (USER_001) 또는 없거나 비활성인 상품 (SHOP_001)",
			content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	@ApiResponse(responseCode = "409", description = "이미 보유한 상품 (SHOP_002) 또는 코인 부족 (SHOP_003)",
			content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	@ApiResponse(responseCode = "500", description = "음수 상품 가격 (SHOP_004) 또는 서버 내부 오류",
			content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	BaseResponse<ShopPurchaseResponse> purchase(
			@Parameter(hidden = true) Long userId,
			@RequestBody(required = true, content = @Content(mediaType = APPLICATION_JSON_VALUE,
					schema = @Schema(implementation = ShopPurchaseRequest.class), examples = @ExampleObject(value = "{\"itemId\":123}")))
			@Valid ShopPurchaseRequest request
	);
}
