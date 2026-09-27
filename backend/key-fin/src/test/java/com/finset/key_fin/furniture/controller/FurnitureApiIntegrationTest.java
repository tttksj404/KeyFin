package com.finset.key_fin.furniture.controller;

import com.finset.key_fin.auth.jwt.JwtTokenProvider;
import com.finset.key_fin.furniture.repository.UserFurnitureRepository;
import com.finset.key_fin.furniture.service.DefaultFurnitureService;
import com.finset.key_fin.support.SpringIntegrationTestSupport;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlConfig;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

import java.util.List;

import static com.finset.key_fin.furniture.FurnitureFixtures.PLACEMENT_JSON;
import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.*;
import static org.springframework.http.MediaType.APPLICATION_JSON;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@Sql(scripts = {"/sql/furniture-cleanup.sql", "/sql/furniture-fixture.sql"}, config = @SqlConfig(encoding = "UTF-8"))
@Sql(scripts = "/sql/furniture-cleanup.sql", executionPhase = Sql.ExecutionPhase.AFTER_TEST_METHOD)
class FurnitureApiIntegrationTest extends SpringIntegrationTestSupport {
	@Autowired private MockMvc mvc;
	@Autowired private JwtTokenProvider tokens;
	@Autowired private JdbcClient jdbc;
	@Autowired private UserFurnitureRepository furnitures;
	@Autowired private DefaultFurnitureService defaults;

	@BeforeEach
	void provideRequiredFurniture() {
		defaults.provision(88001);
	}

	private MockHttpServletRequestBuilder auth(MockHttpServletRequestBuilder request, long userId) {
		return request.header("Authorization", "Bearer " + tokens.generateAccessToken(userId));
	}

	private MockHttpServletRequestBuilder change(long id, String body) {
		return patch("/api/v1/furnitures/" + id).contentType(APPLICATION_JSON).content(body);
	}

	@Test
	void listsOnlyOwnedFurnitureSortedIncludingInactiveAndUnplaced() throws Exception {
		mvc.perform(auth(get("/api/v1/furnitures").param("userId", "88002"), 88001))
				.andExpect(status().isOk()).andExpect(jsonPath("$.data[?(@.defaultFurnitureType == null)].userFurnitureId", contains(88201, 88202, 88203)))
				.andExpect(jsonPath("$.data[0].placed").value(true))
				.andExpect(jsonPath("$.data[2].placed").value(false))
				.andExpect(jsonPath("$.data[2].assetKey").value("desk_old"))
				.andExpect(jsonPath("$.data[2].placementStatus").value(nullValue()))
				.andExpect(jsonPath("$.data[2].positionX").value(nullValue()));
		mvc.perform(auth(get("/api/v1/furnitures").param("slotType", "FLOOR"), 88001))
				.andExpect(status().isOk()).andExpect(jsonPath("$.data[?(@.defaultFurnitureType == null)].userFurnitureId", contains(88201, 88203)));
		mvc.perform(auth(get("/api/v1/furnitures").param("slotType", "WALL"), 88001))
				.andExpect(status().isOk()).andExpect(jsonPath("$.data[*].userFurnitureId", contains(88202)));
		mvc.perform(auth(get("/api/v1/furnitures"), 88003)).andExpect(status().isOk()).andExpect(jsonPath("$.data").isEmpty());
		mvc.perform(auth(get("/api/v1/room"), 88003)).andExpect(status().isOk()).andExpect(jsonPath("$.data.furnitures", hasSize(4)));
	}

	@Test
	void placesMovesAndRemovesWithRoomReadbackAndPreservesOtherFurniture() throws Exception {
		var acquired = furnitures.findById(88203L).orElseThrow().getAcquiredAt();
		mvc.perform(auth(get("/api/v1/room"), 88001)).andExpect(status().isOk())
				.andExpect(jsonPath("$.data.furnitures[?(@.defaultFurnitureType == null)].userFurnitureId", contains(88201, 88202)))
				.andExpect(jsonPath("$.data.avatar.equipped[0].userItemId").value(88301));
		for (int i = 0; i < 2; i++) {
			mvc.perform(auth(change(88203, PLACEMENT_JSON), 88001)).andExpect(status().isOk())
					.andExpect(jsonPath("$.data.userFurnitureId").value(88203))
					.andExpect(jsonPath("$.data.placed").value(true))
					.andExpect(jsonPath("$.data.positionX").value(165.123)).andExpect(jsonPath("$.data.layer").value(-2));
		}
		String moved = PLACEMENT_JSON.replace("FRONT_RIGHT", "FRONT_LEFT")
				.replace("165.123", "327.000").replace("280.456", "0").replace(",\"layer\":-2", "");
		mvc.perform(auth(change(88203, moved), 88001)).andExpect(status().isOk()).andExpect(jsonPath("$.data.layer").value(0));
		mvc.perform(auth(get("/api/v1/room"), 88001)).andExpect(status().isOk())
				.andExpect(jsonPath("$.data.furnitures[?(@.defaultFurnitureType == null)].userFurnitureId", contains(88201, 88202, 88203)))
				.andExpect(jsonPath("$.data.furnitures[2].placementDirection").value("FRONT_LEFT"))
				.andExpect(jsonPath("$.data.furnitures[2].positionX").value(327))
				.andExpect(jsonPath("$.data.furnitures[2].positionY").value(0));
		for (int i = 0; i < 2; i++) {
			mvc.perform(auth(change(88203, "{\"placed\":false}"), 88001)).andExpect(status().isOk())
					.andExpect(jsonPath("$.data.placed").value(false)).andExpect(jsonPath("$.data.placementStatus").value(nullValue()))
					.andExpect(jsonPath("$.data.placementDirection").value(nullValue()))
					.andExpect(jsonPath("$.data.positionX").value(nullValue())).andExpect(jsonPath("$.data.positionY").value(nullValue()))
					.andExpect(jsonPath("$.data.layer").value(0));
		}
		mvc.perform(auth(get("/api/v1/room"), 88001)).andExpect(status().isOk())
				.andExpect(jsonPath("$.data.furnitures[?(@.defaultFurnitureType == null)].userFurnitureId", contains(88201, 88202)));
		assertThat(furnitures.findById(88203L).orElseThrow().getAcquiredAt()).isEqualTo(acquired);
		assertThat(furnitures.findById(88201L).orElseThrow().getPositionX()).isEqualByComparingTo("165.123");
		assertThat(jdbc.sql("SELECT COUNT(*) FROM user_furnitures WHERE user_id = 88001").query(Long.class).single()).isEqualTo(7);
	}

	@ParameterizedTest
	@ValueSource(strings = {"LEFT_WALL", "RIGHT_WALL"})
	void supportsBothWallSurfacesAndCoordinateBoundaries(String surface) throws Exception {
		String body = PLACEMENT_JSON.replace("FLOOR", surface).replace("165.123", "0").replace("280.456", "586.000");
		mvc.perform(auth(change(88202, body), 88001)).andExpect(status().isOk())
				.andExpect(jsonPath("$.data.placementStatus").value(surface));
		assertThat(furnitures.findById(88202L).orElseThrow().getPositionY()).isEqualByComparingTo("586");
	}

	@ParameterizedTest
	@ValueSource(strings = {"404.001", "500.000", "586.000"})
	void persistsFloorPlacementBeyondPreviousYLimit(String positionY) throws Exception {
		String body = PLACEMENT_JSON.replace("280.456", positionY);
		mvc.perform(auth(change(88201, body), 88001)).andExpect(status().isOk())
				.andExpect(jsonPath("$.data.positionY").value(Double.parseDouble(positionY)));
		assertThat(furnitures.findById(88201L).orElseThrow().getPositionY()).isEqualByComparingTo(positionY);
	}

	@ParameterizedTest
	@CsvSource({"88201,LEFT_WALL", "88201,RIGHT_WALL", "88202,FLOOR"})
	void rejectsWrongSurfaceWithoutChangingDatabase(long id, String surface) throws Exception {
		var before = furnitures.findById(id).orElseThrow().getPlacementStatus();
		mvc.perform(auth(change(id, PLACEMENT_JSON.replace("FLOOR", surface)), 88001))
				.andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value("FURNITURE_002"));
		assertThat(furnitures.findById(id).orElseThrow().getPlacementStatus()).isEqualTo(before);
	}

	@Test
	void beanValidationRunsInFullApplicationAndDoesNotMutateDatabase() throws Exception {
		var beforeY = furnitures.findById(88201L).orElseThrow().getPositionY();
		for (String body : List.of("{\"placed\":true}", "{\"placed\":false,\"layer\":0}",
				PLACEMENT_JSON.replace("165.123", "327.001"), PLACEMENT_JSON.replace("280.456", "586.001"),
				PLACEMENT_JSON.replace("280.456", "1.1234"))) {
			mvc.perform(auth(change(88201, body), 88001)).andExpect(status().isBadRequest())
					.andExpect(jsonPath("$.code").value("COMMON_001"));
		}
		assertThat(furnitures.findById(88201L).orElseThrow().getPositionX()).isEqualByComparingTo("165.123");
		assertThat(furnitures.findById(88201L).orElseThrow().getPositionY()).isEqualByComparingTo(beforeY);
	}

	@ParameterizedTest
	@ValueSource(strings = {"", "HEAD", "floor", "UNKNOWN"})
	void rejectsInvalidSlot(String slot) throws Exception {
		mvc.perform(auth(get("/api/v1/furnitures").param("slotType", slot), 88001))
				.andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value("COMMON_001"));
	}

	@ParameterizedTest
	@ValueSource(longs = {88204, 999999})
	void foreignAndMissingFurnitureHaveSameError(long id) throws Exception {
		for (String body : List.of(PLACEMENT_JSON, "{\"placed\":false}")) {
			mvc.perform(auth(change(id, body), 88001)).andExpect(status().isNotFound())
					.andExpect(jsonPath("$.code").value("FURNITURE_001"));
		}
		assertThat(furnitures.findById(88204L).orElseThrow().getPositionX()).isEqualByComparingTo("1");
	}

	@ParameterizedTest
	@ValueSource(longs = {88004, 999999})
	void rejectsDeletedAndMissingUsers(long userId) throws Exception {
		for (var request : List.of(get("/api/v1/furnitures"), get("/api/v1/room"),
				change(88201, PLACEMENT_JSON), change(88201, "{\"placed\":false}"))) {
			mvc.perform(auth(request, userId)).andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("USER_001"));
		}
	}

	@Test
	void allEndpointsRequireAccessTokens() throws Exception {
		for (String token : List.of("", "not-a-jwt", tokens.generateRefreshToken(88001L))) {
			for (var request : List.of(get("/api/v1/furnitures"), get("/api/v1/room"),
					change(88201, PLACEMENT_JSON), change(88201, "{\"placed\":false}"))) {
				if (!token.isEmpty()) request.header("Authorization", "Bearer " + token);
				mvc.perform(request).andExpect(status().isUnauthorized());
			}
		}
	}
}
