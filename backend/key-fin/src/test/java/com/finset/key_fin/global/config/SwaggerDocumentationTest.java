package com.finset.key_fin.global.config;

import com.finset.key_fin.support.SpringIntegrationTestSupport;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.aMapWithSize;
import static org.hamcrest.Matchers.containsInAnyOrder;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class SwaggerDocumentationTest extends SpringIntegrationTestSupport {

	@Autowired
	private MockMvc mockMvc;

	@Test
	void documentsRoomWithCategoryOverrunsWithoutBoard() throws Exception {
		mockMvc.perform(get("/v3/api-docs"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.components.schemas.RoomResponse.properties").value(aMapWithSize(6)))
				.andExpect(jsonPath("$.components.schemas.RoomResponse.properties.avatar").exists())
				.andExpect(jsonPath("$.components.schemas.RoomResponse.properties.furnitures").exists())
				.andExpect(jsonPath("$.components.schemas.RoomResponse.properties.coin").exists())
				.andExpect(jsonPath("$.components.schemas.RoomResponse.properties.attendance").exists())
				.andExpect(jsonPath("$.components.schemas.RoomResponse.properties.stickers").exists())
				.andExpect(jsonPath("$.components.schemas.RoomResponse.properties.overEnvelopes.type").value("array"))
				.andExpect(jsonPath("$.components.schemas.RoomResponse.properties.overEnvelopes.items.type").value("integer"))
				.andExpect(jsonPath("$.components.schemas.RoomResponse.properties.board").doesNotHaveJsonPath())
				.andExpect(jsonPath("$.components.schemas.BoardResponse").doesNotHaveJsonPath())
				.andExpect(jsonPath("$.paths['/api/v1/room'].get.responses['200'].content['application/json'].examples['방 조회 성공'].value.data")
						.value(aMapWithSize(6)))
				.andExpect(jsonPath("$.paths['/api/v1/room'].get.responses['200'].content['application/json'].examples['방 조회 성공'].value.data.overEnvelopes[0]")
						.value(1))
				.andExpect(jsonPath("$.paths['/api/v1/room'].get.responses['200'].content['application/json'].examples['방 조회 성공'].value.data.overEnvelopes[1]")
						.value(4))
				.andExpect(jsonPath("$.paths['/api/v1/room'].get.responses['200'].content['application/json'].examples['방 조회 성공'].value.data.board")
						.doesNotHaveJsonPath());
	}

	@Test
	void documentsItemPatchWithRequiredBooleanAndSharedEquipment() throws Exception {
		mockMvc.perform(get("/v3/api-docs"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.paths['/api/v1/items'].get.parameters[*].name")
						.value(containsInAnyOrder("slotType")))
				.andExpect(jsonPath("$.paths['/api/v1/items'].get.parameters[0].required").value(false))
				.andExpect(jsonPath("$.paths['/api/v1/items'].get.parameters[0].schema.enum")
						.value(containsInAnyOrder("HEAD", "FACE", "UPPER_BODY", "LOWER_BODY", "SOCKS", "FOOTWEAR")))
				.andExpect(jsonPath("$.paths['/api/v1/items'].get.security[0].bearerAuth").exists())
				.andExpect(jsonPath("$.paths['/api/v1/items/{userItemId}/equip']").doesNotExist())
				.andExpect(jsonPath("$.paths['/api/v1/items/{userItemId}']").value(aMapWithSize(1)))
				.andExpect(jsonPath("$.paths['/api/v1/items/{userItemId}'].patch.parameters[*].name")
						.value(containsInAnyOrder("userItemId")))
				.andExpect(jsonPath("$.paths['/api/v1/items/{userItemId}'].patch.requestBody.required").value(true))
				.andExpect(jsonPath("$.paths['/api/v1/items/{userItemId}'].patch.requestBody.content['application/json'].schema['$ref']")
						.value("#/components/schemas/ItemEquipmentUpdateRequest"))
				.andExpect(jsonPath("$.components.schemas.ItemEquipmentUpdateRequest.required")
						.value(containsInAnyOrder("equipped")))
				.andExpect(jsonPath("$.components.schemas.ItemEquipmentUpdateRequest.properties").value(aMapWithSize(1)))
				.andExpect(jsonPath("$.components.schemas.ItemEquipmentUpdateRequest.properties.equipped.type").value("boolean"))
				.andExpect(jsonPath("$.paths['/api/v1/items/{userItemId}'].patch.requestBody.content['application/json'].examples['장착·교체'].value.equipped")
						.value(true))
				.andExpect(jsonPath("$.paths['/api/v1/items/{userItemId}'].patch.requestBody.content['application/json'].examples['해제'].value.equipped")
						.value(false))
				.andExpect(jsonPath("$.paths['/api/v1/items/{userItemId}'].patch.security[0].bearerAuth").exists())
				.andExpect(jsonPath("$.paths['/api/v1/items/{userItemId}'].patch.responses['200'].content['application/json'].schema['$ref']")
						.value("#/components/schemas/BaseResponseAvatarEquipmentResponse"))
				.andExpect(jsonPath("$.paths['/api/v1/items/{userItemId}'].patch.responses['400']").exists())
				.andExpect(jsonPath("$.paths['/api/v1/items/{userItemId}'].patch.responses['404']").exists())
				.andExpect(jsonPath("$.components.schemas.EquippedItemResponse.properties")
						.value(aMapWithSize(4)))
				.andExpect(jsonPath("$.components.schemas.EquippedItemResponse.required")
						.value(containsInAnyOrder("userItemId", "itemId", "slotType", "assetKey")))
				.andExpect(jsonPath("$.components.schemas.AvatarEquipmentResponse.properties.equipped.items['$ref']")
						.value("#/components/schemas/EquippedItemResponse"))
				.andExpect(jsonPath("$.components.schemas.AvatarResponse.properties.equipped.items['$ref']")
						.value("#/components/schemas/EquippedItemResponse"));
	}

	@Test
	void documentsFinCoinBalanceWithoutQueryParameters() throws Exception {
		mockMvc.perform(get("/v3/api-docs"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins/balance'].get.summary").value("코인 최종 잔액 조회"))
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins/balance'].get.parameters").doesNotExist())
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins/balance'].get.security[0].bearerAuth").exists())
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins/balance'].get.responses['200'].content['application/json'].schema['$ref']")
						.value("#/components/schemas/BaseResponseFinCoinBalanceResponse"))
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins/balance'].get.responses['200'].content['application/json'].example.data")
						.value(aMapWithSize(1)))
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins/balance'].get.responses['200'].content['application/json'].example.data.balance")
						.value(1250))
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins/balance'].get.responses['401']").exists())
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins/balance'].get.responses['403']").exists())
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins/balance'].get.responses['404']").exists())
				.andExpect(jsonPath("$.components.schemas.BaseResponseFinCoinBalanceResponse.properties.data['$ref']")
						.value("#/components/schemas/FinCoinBalanceResponse"))
				.andExpect(jsonPath("$.components.schemas.FinCoinBalanceResponse.properties").value(aMapWithSize(1)))
				.andExpect(jsonPath("$.components.schemas.FinCoinBalanceResponse.properties.balance.type").value("integer"))
				.andExpect(jsonPath("$.components.schemas.FinCoinBalanceResponse.properties.balance.format").value("int32"))
				.andExpect(jsonPath("$.components.schemas.FinCoinBalanceResponse.required").value(containsInAnyOrder("balance")));
	}

	@Test
	void documentsFinCoinQueryParametersAndActualResponseTypes() throws Exception {
		mockMvc.perform(get("/v3/api-docs"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.paths['/api/v1/coins']").doesNotExist())
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins'].get.summary").value("코인 이력 조회"))
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins'].get.security[0].bearerAuth").exists())
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins'].get.parameters[*].name")
						.value(containsInAnyOrder("cursor", "size")))
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins'].get.parameters[?(@.name == 'cursor')].required")
						.value(containsInAnyOrder(false)))
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins'].get.parameters[?(@.name == 'cursor')].schema.format")
						.value(containsInAnyOrder("int64")))
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins'].get.parameters[?(@.name == 'cursor')].schema.minimum")
						.value(containsInAnyOrder(1)))
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins'].get.parameters[?(@.name == 'size')].required")
						.value(containsInAnyOrder(false)))
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins'].get.parameters[?(@.name == 'size')].schema.default")
						.value(containsInAnyOrder(20)))
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins'].get.parameters[?(@.name == 'size')].schema.minimum")
						.value(containsInAnyOrder(1)))
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins'].get.parameters[?(@.name == 'size')].schema.maximum")
						.value(containsInAnyOrder(100)))
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins'].get.responses['200'].content['application/json'].schema['$ref']")
						.value("#/components/schemas/BaseResponseFinCoinResponse"))
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins'].get.responses['200'].content['application/json'].example.data")
						.value(aMapWithSize(2)))
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins'].get.responses['200'].content['application/json'].example.data.balance")
						.doesNotHaveJsonPath())
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins'].get.responses['200'].content['application/json'].example.data.items[0].balanceAfter")
						.value(1250))
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins'].get.responses['200'].content['application/json'].example.data.nextCursor")
						.value(nullValue()))
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins'].get.responses['400']").exists())
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins'].get.responses['401']").exists())
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins'].get.responses['403']").exists())
				.andExpect(jsonPath("$.paths['/api/v1/fin-coins'].get.responses['404']").exists())
				.andExpect(jsonPath("$.components.schemas.BaseResponseFinCoinResponse.properties.data['$ref']")
						.value("#/components/schemas/FinCoinResponse"))
				.andExpect(jsonPath("$.components.schemas.FinCoinResponse.properties").value(aMapWithSize(2)))
				.andExpect(jsonPath("$.components.schemas.FinCoinResponse.properties.balance").doesNotHaveJsonPath())
				.andExpect(jsonPath("$.components.schemas.FinCoinResponse.required").value(containsInAnyOrder("items", "nextCursor")))
				.andExpect(jsonPath("$.components.schemas.FinCoinResponse.properties.nextCursor.type")
						.value(containsInAnyOrder("integer", "null")))
				.andExpect(jsonPath("$.components.schemas.FinCoinResponse.properties.nextCursor.format").value("int64"))
				.andExpect(jsonPath("$.components.schemas.FinCoinHistoryResponse.properties.id.format").value("int64"))
				.andExpect(jsonPath("$.components.schemas.FinCoinHistoryResponse.properties.delta.format").value("int32"))
				.andExpect(jsonPath("$.components.schemas.FinCoinHistoryResponse.properties.balanceAfter.format").value("int32"))
				.andExpect(jsonPath("$.components.schemas.FinCoinHistoryResponse.required")
						.value(containsInAnyOrder("id", "delta", "balanceAfter", "reasonCode", "reasonText", "grantDate")))
				.andExpect(jsonPath("$.components.schemas.FinCoinHistoryResponse.properties.reasonCode.enum")
						.value(containsInAnyOrder("ATTEND", "CONFIRM_ALL", "WEEKLY", "MONTHLY", "PURCHASE")))
				.andExpect(jsonPath("$.components.schemas.FinCoinHistoryResponse.properties.grantDate.format").value("date"));
	}

	@Test
	void exposesOpenApiDocumentWithBearerSchemeAndAuthOperations() throws Exception {
		mockMvc.perform(get("/v3/api-docs"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.info.title").value("KeyFin API"))
				.andExpect(jsonPath("$.components.securitySchemes.bearerAuth.type").value("http"))
				.andExpect(jsonPath("$.components.securitySchemes.bearerAuth.scheme").value("bearer"))
				.andExpect(jsonPath("$.paths['/api/v1/auth/signup'].post.summary").value("회원가입"))
				.andExpect(jsonPath("$.paths['/api/v1/auth/signup'].post.responses['201']").exists())
				.andExpect(jsonPath("$.paths['/api/v1/auth/signup'].post.responses['409']").exists())
				.andExpect(jsonPath("$.paths['/api/v1/auth/login'].post.summary").value("로그인"))
				.andExpect(jsonPath("$.paths['/api/v1/auth/login'].post.responses['200']").exists())
				.andExpect(jsonPath("$.paths['/api/v1/auth/login'].post.responses['401']").exists())
				.andExpect(jsonPath("$.paths['/api/v1/auth/refresh'].post.summary").value("Access Token 재발급"))
				.andExpect(jsonPath("$.paths['/api/v1/auth/refresh'].post.responses['401']").exists())
				.andExpect(jsonPath("$.paths['/api/v1/auth/logout'].post.summary").value("로그아웃"))
				.andExpect(jsonPath("$.paths['/api/v1/auth/logout'].post.security[0].bearerAuth").exists())
				.andExpect(jsonPath("$.paths['/api/v1/auth/logout'].post.responses['401']").exists())
				.andExpect(jsonPath("$.paths['/api/v1/links/connect'].post.summary").value("금융망 회원 연결"))
				.andExpect(jsonPath("$.paths['/api/v1/links/connect'].post.security[0].bearerAuth").exists())
				.andExpect(jsonPath("$.paths['/api/v1/links/connect'].post.requestBody.required").value(true))
				.andExpect(jsonPath("$.paths['/api/v1/links/connect'].post.responses['409']").exists())
				.andExpect(jsonPath("$.paths['/api/v1/links/status'].get.summary").value("금융망 연결 상태 조회"))
				.andExpect(jsonPath("$.paths['/api/v1/links/status'].get.security[0].bearerAuth").exists());
	}
}
