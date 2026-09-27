package com.finset.key_fin.item.controller;

import com.finset.key_fin.auth.jwt.JwtTokenProvider;
import com.finset.key_fin.furniture.repository.UserFurnitureRepository;
import com.finset.key_fin.support.SpringIntegrationTestSupport;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlConfig;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.hasSize;
import static org.springframework.http.MediaType.APPLICATION_JSON;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@Transactional
@Sql(scripts = "/sql/item-fixture.sql", config = @SqlConfig(encoding = "UTF-8"))
class ItemApiIntegrationTest extends SpringIntegrationTestSupport {
	@Autowired private MockMvc mvc;
	@Autowired private JwtTokenProvider tokens;
	@Autowired private JdbcClient jdbc;
	@Autowired private UserFurnitureRepository furniture;

	private MockHttpServletRequestBuilder auth(MockHttpServletRequestBuilder request, long userId) {
		return request.header("Authorization", "Bearer " + tokens.generateAccessToken(userId));
	}

	private MockHttpServletRequestBuilder equipmentRequest(String id, boolean equipped) {
		return patch("/api/v1/items/" + id).contentType(APPLICATION_JSON)
				.content("{\"equipped\":" + equipped + "}");
	}

	@Test
	void returnsOwnedItemsInIdOrderIncludingInactiveCatalogItemAndPreservesFurnitureMapping() throws Exception {
		mvc.perform(auth(get("/api/v1/items").param("userId", "972"), 971))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data", hasSize(7)))
				.andExpect(jsonPath("$.data[*].userItemId", contains(7201, 7202, 7203, 7204, 7205, 7206, 7207)))
				.andExpect(jsonPath("$.data[0].equipped").value(true))
				.andExpect(jsonPath("$.data[1].equipped").value(false))
				.andExpect(jsonPath("$.data[1].itemId").value(7104))
				.andExpect(jsonPath("$.data[1].assetKey").value("shirt_b"));
		assertThat(furniture.findById(7301L).orElseThrow().getItem().getId()).isEqualTo(7108L);
	}

	@ParameterizedTest
	@CsvSource({"HEAD,1", "FACE,1", "UPPER_BODY,2", "LOWER_BODY,1", "SOCKS,1", "FOOTWEAR,1"})
	void filtersEveryAvatarSlot(String slot, int size) throws Exception {
		mvc.perform(auth(get("/api/v1/items").param("slotType", slot), 971))
				.andExpect(status().isOk()).andExpect(jsonPath("$.data", hasSize(size)))
				.andExpect(jsonPath("$.data[0].slotType").value(slot));
	}

	@Test
	void emptyWardrobeHasNoSyntheticDefaultItems() throws Exception {
		mvc.perform(auth(get("/api/v1/items"), 973)).andExpect(status().isOk())
				.andExpect(jsonPath("$.data").isEmpty());
		mvc.perform(auth(get("/api/v1/items").param("slotType", "HEAD"), 973))
				.andExpect(status().isOk()).andExpect(jsonPath("$.data").isEmpty());
		mvc.perform(auth(get("/api/v1/room"), 973)).andExpect(status().isOk())
				.andExpect(jsonPath("$.data.avatar.equipped").isEmpty());
	}

	@Test
	void replacesClothesAndReturnsFullEquipmentMatchingRoomThenAllowsRemovingEverything() throws Exception {
		// 비활성 상품도 이미 보유했다면 장착할 수 있다.
		for (int attempt = 0; attempt < 2; attempt++) {
			mvc.perform(auth(equipmentRequest("7202", true), 971))
					.andExpect(status().isOk())
					.andExpect(jsonPath("$.data.equipped[*].userItemId", contains(7203, 7202)))
					.andExpect(jsonPath("$.data.equipped[*].slotType", contains("HEAD", "UPPER_BODY")));
		}
		// 이전 상의 해제 요청은 교체된 상의를 해제하지 않는다.
		mvc.perform(auth(equipmentRequest("7201", false), 971))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.equipped[*].userItemId", contains(7203, 7202)));
		mvc.perform(auth(get("/api/v1/room"), 971)).andExpect(status().isOk())
				.andExpect(jsonPath("$.data.avatar.equipped[*].userItemId", contains(7203, 7202)))
				.andExpect(jsonPath("$.data.avatar.equipped[1].assetKey").value("shirt_b"));
		mvc.perform(auth(equipmentRequest("7202", false), 971))
				.andExpect(status().isOk()).andExpect(jsonPath("$.data.equipped[*].userItemId", contains(7203)));
		for (int attempt = 0; attempt < 2; attempt++) {
			mvc.perform(auth(equipmentRequest("7203", false), 971))
					.andExpect(status().isOk()).andExpect(jsonPath("$.data.equipped").isEmpty());
		}
		mvc.perform(auth(get("/api/v1/room"), 971))
				.andExpect(status().isOk()).andExpect(jsonPath("$.data.avatar.equipped").isEmpty());
		assertThat(jdbc.sql("SELECT COUNT(*) FROM user_items WHERE user_id = 971").query(Long.class).single())
				.isEqualTo(7);
		assertThat(jdbc.sql("SELECT equipped_slot FROM user_items WHERE id = 7208")
				.query(String.class).single()).isEqualTo("HEAD");
	}

	@ParameterizedTest
	@CsvSource({"7203,HEAD", "7204,FACE", "7201,UPPER_BODY", "7205,LOWER_BODY", "7206,SOCKS", "7207,FOOTWEAR"})
	void everyPartCanBeEquippedAndRemoved(long id, String slot) throws Exception {
		mvc.perform(auth(equipmentRequest(String.valueOf(id), true), 971)).andExpect(status().isOk());
		assertThat(jdbc.sql("SELECT equipped_slot FROM user_items WHERE id = :id").param("id", id)
				.query(String.class).single()).isEqualTo(slot);
		mvc.perform(auth(equipmentRequest(String.valueOf(id), false), 971)).andExpect(status().isOk());
		assertThat(jdbc.sql("SELECT COUNT(*) FROM user_items WHERE id = :id AND equipped_slot IS NULL")
				.param("id", id).query(Long.class).single()).isEqualTo(1);
	}

	@ParameterizedTest
	@ValueSource(strings = {"", " ", "WALL", "FLOOR", "UNKNOWN", "upper_body"})
	void rejectsInvalidSlot(String slot) throws Exception {
		mvc.perform(auth(get("/api/v1/items").param("slotType", slot), 971))
				.andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value("COMMON_001"));
	}

	@ParameterizedTest
	@ValueSource(strings = {"0", "-1", "text", "9223372036854775808"})
	void rejectsInvalidIds(String id) throws Exception {
		for (var request : List.of(equipmentRequest(id, true), equipmentRequest(id, false))) {
			mvc.perform(auth(request, 971)).andExpect(status().isBadRequest())
					.andExpect(jsonPath("$.code").value("COMMON_001"));
		}
	}

	@ParameterizedTest
	@ValueSource(strings = {"{}", "{\"equipped\":null}"})
	void rejectsMissingEquipmentStateWithoutUnequipping(String body) throws Exception {
		mvc.perform(auth(patch("/api/v1/items/7201").contentType(APPLICATION_JSON).content(body), 971))
				.andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value("COMMON_001"));
		assertThat(jdbc.sql("SELECT equipped_slot FROM user_items WHERE id = 7201")
				.query(String.class).single()).isEqualTo("UPPER_BODY");
	}

	@ParameterizedTest
	@ValueSource(strings = {"", "{", "null", "{\"equipped\":[]}"})
	void rejectsMissingOrUnreadableBody(String body) throws Exception {
		mvc.perform(auth(patch("/api/v1/items/7201").contentType(APPLICATION_JSON).content(body), 971))
				.andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value("COMMON_002"));
	}

	@Test
	void legacyEquipEndpointsAreRemoved() throws Exception {
		for (var request : List.of(put("/api/v1/items/7202/equip"), delete("/api/v1/items/7201/equip"))) {
			mvc.perform(auth(request, 971)).andExpect(status().isNotFound());
		}
		mvc.perform(auth(get("/api/v1/room"), 971)).andExpect(status().isOk())
				.andExpect(jsonPath("$.data.avatar.equipped[*].userItemId", contains(7203, 7201)));
	}

	@ParameterizedTest
	@ValueSource(longs = {7208, 999999})
	void foreignAndMissingItemsAreIndistinguishable(long id) throws Exception {
		for (var request : List.of(equipmentRequest(String.valueOf(id), true),
				equipmentRequest(String.valueOf(id), false))) {
			mvc.perform(auth(request, 971)).andExpect(status().isNotFound())
					.andExpect(jsonPath("$.code").value("ITEM_001"));
		}
	}

	@ParameterizedTest
	@ValueSource(longs = {974, 999999})
	void rejectsDeletedAndMissingUsers(long id) throws Exception {
		for (var request : List.of(get("/api/v1/items"), get("/api/v1/room"),
				equipmentRequest("7201", true), equipmentRequest("7201", false))) {
			mvc.perform(auth(request, id)).andExpect(status().isNotFound())
					.andExpect(jsonPath("$.code").value("USER_001"));
		}
	}

	@Test
	void allNewEndpointsRequireAccessTokens() throws Exception {
		for (String token : List.of("", "not-a-jwt", tokens.generateRefreshToken(971L))) {
			for (var request : List.of(get("/api/v1/items"), equipmentRequest("7201", true),
					equipmentRequest("7201", false))) {
				if (!token.isEmpty()) request.header("Authorization", "Bearer " + token);
				mvc.perform(request).andExpect(status().isUnauthorized());
			}
		}
	}
}
