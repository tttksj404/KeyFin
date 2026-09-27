package com.finset.key_fin.furniture;

import com.finset.key_fin.auth.dto.request.SignupRequest;
import com.finset.key_fin.auth.jwt.JwtTokenProvider;
import com.finset.key_fin.auth.service.AuthService;
import com.finset.key_fin.furniture.entity.DefaultFurnitureType;
import com.finset.key_fin.furniture.entity.FurniturePlacementDirection;
import com.finset.key_fin.furniture.entity.FurniturePlacementStatus;
import com.finset.key_fin.furniture.service.DefaultFurnitureService;
import com.finset.key_fin.furniture.service.FurnitureService;
import com.finset.key_fin.room.service.RoomService;
import com.finset.key_fin.support.SpringIntegrationTestSupport;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.repository.UserRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.transaction.annotation.Transactional;

import java.sql.SQLException;
import java.util.UUID;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.hamcrest.Matchers.*;
import static org.springframework.http.MediaType.APPLICATION_JSON;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@Transactional
class DefaultFurnitureIntegrationTest extends SpringIntegrationTestSupport {

	@Autowired private AuthService auth;
	@Autowired private UserRepository users;
	@Autowired private DefaultFurnitureService defaults;
	@Autowired private FurnitureService furnitures;
	@Autowired private RoomService rooms;
	@Autowired private JdbcClient jdbc;
	@Autowired private MockMvc mvc;
	@Autowired private JwtTokenProvider tokens;

	@Test
	void signupInstallsFourDefaultsAtInitialPositionsAndRoomReturnsThem() {
		long userId = signup();
		var owned = furnitures.getFurnitures(userId, null);
		assertThat(owned).hasSize(4).allSatisfy(f -> {
			assertThat(f.placed()).isTrue();
			assertThat(f.canUnplace()).isFalse();
			assertThat(f.placementStatus()).isEqualTo(FurniturePlacementStatus.FLOOR);
			assertThat(f.placementDirection()).isEqualTo(FurniturePlacementDirection.FRONT_RIGHT);
			assertThat(f.layer()).isZero();
			switch (f.defaultFurnitureType()) {
				case DINING_TABLE -> {
					assertThat(f.positionX()).isEqualByComparingTo("64.604");
					assertThat(f.positionY()).isEqualByComparingTo("362.438");
				}
				case COFFEE_TABLE -> {
					assertThat(f.positionX()).isEqualByComparingTo("127.417");
					assertThat(f.positionY()).isEqualByComparingTo("429.875");
				}
				case SOFA -> {
					assertThat(f.positionX()).isEqualByComparingTo("198.125");
					assertThat(f.positionY()).isEqualByComparingTo("443.250");
				}
				case TV -> {
					assertThat(f.positionX()).isEqualByComparingTo("190.625");
					assertThat(f.positionY()).isEqualByComparingTo("334.688");
				}
			}
		});
		assertThat(owned).extracting(f -> f.defaultFurnitureType())
				.containsExactlyInAnyOrder(DefaultFurnitureType.values());
		assertThat(rooms.getRoom(userId).furnitures()).extracting(f -> f.userFurnitureId())
				.containsExactlyElementsOf(owned.stream().map(f -> f.userFurnitureId()).toList());
	}

	@Test
	void provisioningReusesOwnedFurnitureFillsMissingAndPreservesPlacement() {
		long userId = users.save(User.create(UUID.randomUUID() + "@defaults.test", "encoded", "가구테스터")).getId();
		jdbc.sql("""
				INSERT INTO user_furnitures (user_id, item_id, placement_status, placement_direction, position_x, position_y, layer)
				SELECT :user, id, IF(default_furniture_type = 'SOFA', 'FLOOR', NULL),
				       IF(default_furniture_type = 'SOFA', 'FRONT_LEFT', NULL),
				       IF(default_furniture_type = 'SOFA', 100.123, NULL),
				       IF(default_furniture_type = 'SOFA', 200.456, NULL),
				       IF(default_furniture_type = 'SOFA', 2, 0)
				FROM items WHERE default_furniture_type IN ('DINING_TABLE', 'SOFA')
				""").param("user", userId).update();
		var originalIds = furnitures.getFurnitures(userId, null).stream().map(f -> f.userFurnitureId()).toList();
		defaults.provision(userId);
		defaults.provision(userId);
		var owned = furnitures.getFurnitures(userId, null);
		assertThat(owned).hasSize(4).allSatisfy(f -> assertThat(f.placed()).isTrue());
		assertThat(owned).extracting(f -> f.userFurnitureId()).containsAll(originalIds);
		var sofa = owned.stream().filter(f -> f.defaultFurnitureType() == DefaultFurnitureType.SOFA).findFirst().orElseThrow();
		assertThat(sofa.positionX()).isEqualByComparingTo("100.123");
		assertThat(sofa.positionY()).isEqualByComparingTo("200.456");
		assertThat(sofa.placementDirection()).isEqualTo(FurniturePlacementDirection.FRONT_LEFT);
		assertThat(sofa.layer()).isEqualTo(2);
		var diningTable = owned.stream().filter(f -> f.defaultFurnitureType() == DefaultFurnitureType.DINING_TABLE).findFirst().orElseThrow();
		assertThat(diningTable.positionX()).isEqualByComparingTo("64.604");
		assertThat(diningTable.positionY()).isEqualByComparingTo("362.438");
	}

	@Test
	void defaultsCanMoveButCannotBeUnplaced() throws Exception {
		long userId = signup();
		var owned = furnitures.getFurnitures(userId, null);
		for (var furniture : owned) {
			mvc.perform(authenticated(patch("/api/v1/furnitures/" + furniture.userFurnitureId())
					.contentType(APPLICATION_JSON).content("{\"placed\":false}"), userId))
					.andExpect(status().isConflict()).andExpect(jsonPath("$.code").value("FURNITURE_003"));
		}
		long sofa = owned.stream().filter(f -> f.defaultFurnitureType() == DefaultFurnitureType.SOFA)
				.findFirst().orElseThrow().userFurnitureId();
		mvc.perform(authenticated(patch("/api/v1/furnitures/" + sofa).contentType(APPLICATION_JSON).content("""
				{"placed":true,"placementStatus":"FLOOR","placementDirection":"FRONT_LEFT","positionX":100.123,"positionY":200.456,"layer":2}
				"""), userId)).andExpect(status().isOk())
				.andExpect(jsonPath("$.data.defaultFurnitureType").value("SOFA"))
				.andExpect(jsonPath("$.data.canUnplace").value(false));
		defaults.provision(userId);
		var placed = rooms.getRoom(userId).furnitures().stream().filter(f -> f.userFurnitureId() == sofa).findFirst().orElseThrow();
		assertThat(placed.positionX()).isEqualByComparingTo("100.123");
		assertThat(placed.placementDirection()).isEqualTo(FurniturePlacementDirection.FRONT_LEFT);
	}

	@Test
	void defaultsAreExcludedFromShopAndCannotBePurchased() throws Exception {
		long userId = signup();
		for (var furniture : furnitures.getFurnitures(userId, null)) {
			mvc.perform(authenticated(get("/api/v1/shop"), userId)).andExpect(status().isOk())
					.andExpect(jsonPath("$.data[*].itemId", not(hasItem(furniture.itemId().intValue()))));
			mvc.perform(authenticated(post("/api/v1/shop/purchase").contentType(APPLICATION_JSON)
					.content("{\"itemId\":" + furniture.itemId() + "}"), userId)).andExpect(status().isNotFound());
		}
	}

	@ParameterizedTest(name = "{0}")
	@MethodSource("invalidFurnitureUpdates")
	void databaseRejectsInvalidFurnitureCatalogChanges(String scenario, String sql, String constraint) {
		assertThatThrownBy(() -> jdbc.sql(sql).update())
				.isInstanceOf(DataAccessException.class)
				.rootCause().isInstanceOfSatisfying(SQLException.class, exception -> {
					assertThat(exception.getErrorCode()).isEqualTo(3819);
					assertThat(exception.getMessage()).contains(constraint);
				});
	}

	private static Stream<Arguments> invalidFurnitureUpdates() {
		return Stream.of(
				Arguments.of("기본 가구 판매 활성화 거절",
						"UPDATE items SET is_active = TRUE WHERE default_furniture_type = 'TV'",
						"chk_default_furniture"),
				Arguments.of("기본 가구 유형 NULL 거절",
						"UPDATE items SET furniture_type = NULL WHERE asset_key = 'sofa_default'",
						"chk_default_furniture_type_match"),
				Arguments.of("기본 가구 유형 불일치 거절",
						"UPDATE items SET furniture_type = 'TV' WHERE asset_key = 'sofa_default'",
						"chk_default_furniture_type_match"),
				Arguments.of("벽 가구의 필수 가구 유형 지정 거절",
						"UPDATE items SET furniture_type = 'SOFA' WHERE asset_key = 'decor_round_mirror'",
						"chk_furniture_type"),
				Arguments.of("허용되지 않은 가구 유형 거절",
						"UPDATE items SET furniture_type = 'OTHER' WHERE asset_key = 'desk_original'",
						"chk_furniture_type")
		);
	}

	private long signup() {
		return auth.signup(new SignupRequest(UUID.randomUUID() + "@defaults.test", "Passw0rd!", "가구테스터")).userId();
	}

	private MockHttpServletRequestBuilder authenticated(MockHttpServletRequestBuilder request, long userId) {
		return request.header("Authorization", "Bearer " + tokens.generateAccessToken(userId));
	}
}
