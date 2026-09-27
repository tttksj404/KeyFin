package com.finset.key_fin.furniture;

import com.finset.key_fin.auth.jwt.JwtTokenProvider;
import com.finset.key_fin.furniture.dto.request.FurniturePlacementsUpdateRequest;
import com.finset.key_fin.furniture.dto.request.FurniturePlacementsUpdateRequest.Placement;
import com.finset.key_fin.furniture.dto.response.UserFurnitureResponse;
import com.finset.key_fin.furniture.entity.FurnitureType;
import com.finset.key_fin.furniture.service.DefaultFurnitureService;
import com.finset.key_fin.furniture.service.FurnitureService;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.room.service.RoomService;
import com.finset.key_fin.room.service.RoomStickerService;
import com.finset.key_fin.support.SpringIntegrationTestSupport;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.repository.UserRepository;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import tools.jackson.databind.json.JsonMapper;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

import static com.finset.key_fin.furniture.entity.FurniturePlacementDirection.FRONT_LEFT;
import static com.finset.key_fin.furniture.entity.FurniturePlacementStatus.FLOOR;
import static com.finset.key_fin.furniture.entity.FurniturePlacementStatus.LEFT_WALL;
import static org.assertj.core.api.Assertions.*;
import static org.hamcrest.Matchers.hasSize;
import static org.springframework.http.MediaType.APPLICATION_JSON;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@Timeout(60)
class FurniturePlacementsIntegrationTest extends SpringIntegrationTestSupport {
	@Autowired private UserRepository users;
	@Autowired private DefaultFurnitureService defaults;
	@Autowired private FurnitureService service;
	@Autowired private RoomService rooms;
	@Autowired private RoomStickerService stickers;
	@Autowired private JdbcClient jdbc;
	@Autowired private MockMvc mvc;
	@Autowired private JwtTokenProvider tokens;
	@Autowired private PlatformTransactionManager transactions;
	private final JsonMapper json = JsonMapper.builder().build();
	private final Map<FurnitureType, Long> starter = new EnumMap<>(FurnitureType.class);
	private long userId;
	private long otherId;
	private long sofa;
	private long pinkSofa;
	private long fridge;
	private long tv;
	private long diningTable;
	private long coffeeTable;
	private long desk;

	@BeforeEach
	void setUp() {
		userId = users.save(User.create(UUID.randomUUID() + "@batch.test", "encoded", "배치테스터")).getId();
		otherId = users.save(User.create(UUID.randomUUID() + "@batch.test", "encoded", "다른사용자")).getId();
		defaults.provision(userId).forEach(f -> starter.put(f.getItem().getFurnitureType(), f.getId()));
		sofa = acquire(userId, "sofa_black");
		pinkSofa = acquire(userId, "sofa_pink");
		fridge = acquire(userId, "refrigerator_black");
		tv = acquire(userId, "tv_set_black");
		diningTable = acquire(userId, "dining_table_black");
		coffeeTable = acquire(userId, "coffee_table_black");
		desk = acquire(userId, "desk_original");
	}

	@AfterEach
	void cleanUp() {
		for (long id : List.of(userId, otherId)) {
			jdbc.sql("DELETE FROM user_furnitures WHERE user_id = :id").param("id", id).update();
			users.deleteById(id);
		}
	}

	@Test
	void savesCompleteLayoutAndReplacesAllFourTypesWithStickerInheritance() throws Exception {
		attachAll();
		var request = new FurniturePlacementsUpdateRequest(List.of(entry(sofa), entry(diningTable), entry(coffeeTable), entry(tv), entry(desk)));
		var before = owned();
		mvc.perform(auth(put("/api/v1/furnitures/placements").contentType(APPLICATION_JSON).content(json.writeValueAsString(request))))
				.andExpect(status().isOk()).andExpect(jsonPath("$.data", hasSize(11)))
				.andExpect(jsonPath("$.data[?(@.placed == true)]", hasSize(5)));
		var saved = owned();
		assertThat(saved).extracting(UserFurnitureResponse::userFurnitureId).isSorted();
		assertThat(saved).extracting(UserFurnitureResponse::userFurnitureId).containsExactlyElementsOf(
				before.stream().map(UserFurnitureResponse::userFurnitureId).toList());
		assertThat(saved).filteredOn(f -> f.placed() && f.furnitureType() != null).allSatisfy(f -> {
			assertThat(f.defaultFurnitureType()).isNull();
			assertThat(f.stickerAttached()).isTrue();
			assertThat(f.canUnplace()).isFalse();
			assertThat(f.positionY()).isEqualByComparingTo("586");
		});
		assertThat(saved).filteredOn(f -> f.defaultFurnitureType() != null).allSatisfy(f -> {
			assertThat(f.placed()).isFalse();
			assertThat(f.positionX()).isNull();
			assertThat(f.stickerAttached()).isFalse();
			assertThat(f.canUnplace()).isTrue();
		});
		assertThat(service.updatePlacements(userId, request)).isEqualTo(saved);
		for (int i = 0; i < 2; i++) {
			defaults.provision(userId);
			assertThat(rooms.getRoom(userId).furnitures()).extracting(f -> f.userFurnitureId())
					.containsExactly(sofa, tv, diningTable, coffeeTable, desk);
			assertThat(stickers.synchronize(userId).count()).isEqualTo(4);
		}
		service.updatePlacements(userId, layout(starter.get(FurnitureType.SOFA)));
		assertThat(current(sofa).placed()).isFalse();
		assertThat(current(desk).placed()).isFalse();
		assertThat(current(desk).positionY()).isNull();
		assertThat(current(starter.get(FurnitureType.SOFA)).stickerAttached()).isTrue();
	}

	@Test
	void omittedLayerAndNullLayerDefaultToZero() throws Exception {
		String body = json.writeValueAsString(layout(sofa));
		for (String changed : List.of(body.replace(",\"layer\":-2", ""), body.replace("\"layer\":-2", "\"layer\":null"))) {
			mvc.perform(auth(put("/api/v1/furnitures/placements").contentType(APPLICATION_JSON).content(changed)))
					.andExpect(status().isOk());
			assertThat(current(sofa).layer()).isZero();
		}
	}

	@Test
	void rejectsMissingAndDuplicateTypesWithoutAnyMutation() throws Exception {
		var before = owned();
		for (var type : FurnitureType.values()) {
			var entries = new ArrayList<>(layout(starter.get(FurnitureType.SOFA)).placements());
			entries.removeIf(p -> p.userFurnitureId().equals(starter.get(type)));
			assertRejected(new FurniturePlacementsUpdateRequest(entries), 409, "FURNITURE_004");
			var duplicate = new ArrayList<>(layout(starter.get(FurnitureType.SOFA)).placements());
			duplicate.add(entry(switch (type) {
				case SOFA -> sofa;
				case TV -> tv;
				case DINING_TABLE -> diningTable;
				case COFFEE_TABLE -> coffeeTable;
			}));
			assertRejected(new FurniturePlacementsUpdateRequest(duplicate), 409, "FURNITURE_004");
		}
		var duplicateType = new ArrayList<>(layout(sofa).placements());
		duplicateType.add(entry(pinkSofa));
		assertRejected(new FurniturePlacementsUpdateRequest(duplicateType), 409, "FURNITURE_004");
		assertRejected(new FurniturePlacementsUpdateRequest(List.of()), 409, "FURNITURE_004");
		assertThat(owned()).isEqualTo(before);
	}

	@Test
	void fridgesAreOptionalAndDifferentStylesCanBeInstalledAndUnplaced() throws Exception {
		long pinkFridge = acquire(userId, "refrigerator_pink");
		long oldFridge = acquire(userId, "fridge_default");
		var entries = new ArrayList<>(layout(sofa).placements());
		entries.addAll(List.of(entry(fridge), entry(pinkFridge), entry(oldFridge)));
		service.updatePlacements(userId, new FurniturePlacementsUpdateRequest(entries));
		for (long id : List.of(fridge, pinkFridge, oldFridge)) {
			assertThat(current(id).furnitureType()).isNull();
			assertThat(current(id).defaultFurnitureType()).isNull();
			assertThat(current(id).canUnplace()).isTrue();
			assertThat(current(id).stickerAttached()).isFalse();
			mvc.perform(auth(patch("/api/v1/furnitures/" + id).contentType(APPLICATION_JSON).content("{\"placed\":false}")))
					.andExpect(status().isOk()).andExpect(jsonPath("$.data.placed").value(false));
		}
		service.updatePlacements(userId, layout(sofa));
		assertThat(rooms.getRoom(userId).furnitures()).hasSize(4);
	}

	@Test
	void rejectsDuplicateForeignMissingIdsAndWrongSurfaceAtomically() throws Exception {
		var before = owned();
		var duplicate = new ArrayList<>(layout(sofa).placements());
		duplicate.add(entry(sofa));
		assertRejected(new FurniturePlacementsUpdateRequest(duplicate), 400, "COMMON_001");
		assertRejected(layout(acquire(otherId, "sofa_black")), 404, "FURNITURE_001");
		assertRejected(layout(Long.MAX_VALUE), 404, "FURNITURE_001");
		var entries = new ArrayList<>(layout(sofa).placements());
		entries.set(2, new Placement(sofa, LEFT_WALL, FRONT_LEFT, BigDecimal.ONE, BigDecimal.TEN, 0));
		assertRejected(new FurniturePlacementsUpdateRequest(entries), 400, "FURNITURE_002");
		assertThat(owned()).isEqualTo(before);
	}

	@ParameterizedTest
	@CsvSource(value = {
			"userFurnitureId|0|COMMON_001", "userFurnitureId|null|COMMON_001",
			"positionX|327.001|COMMON_001", "positionX|-0.001|COMMON_001",
			"positionY|586.001|COMMON_001", "positionY|-0.001|COMMON_001", "positionY|1.1234|COMMON_001",
			"placementStatus|null|COMMON_001", "placementDirection|null|COMMON_001",
			"layer|1.5|COMMON_002", "layer|\"1\"|COMMON_002", "layer|2147483648|COMMON_002"
	}, delimiter = '|')
	void validatesNestedEntryBeforeCallingService(String field, String value, String code) throws Exception {
		var fields = entryFields();
		fields.put(field, value);
		assertInvalidBody(bodyOf(fields), code);
	}

	@ParameterizedTest
	@ValueSource(strings = {"userFurnitureId", "positionX", "positionY", "placementStatus", "placementDirection"})
	void requiresEveryPlacementField(String field) throws Exception {
		var fields = entryFields();
		fields.remove(field);
		assertInvalidBody(bodyOf(fields), "COMMON_001");
	}

	@ParameterizedTest
	@ValueSource(strings = {"{}", "{\"placements\":null}", "{\"placements\":[null]}"})
	void rejectsMissingListAndNullElements(String body) throws Exception {
		assertInvalidBody(body, "COMMON_001");
	}

	@Test
	void limitsRequestSizeAndRequiresAuthentication() throws Exception {
		assertRejected(new FurniturePlacementsUpdateRequest(java.util.Collections.nCopies(101, entry(sofa))), 400, "COMMON_001");
		mvc.perform(put("/api/v1/furnitures/placements").contentType(APPLICATION_JSON).content(json.writeValueAsString(layout(sofa))))
				.andExpect(status().isUnauthorized());
	}

	@Test
	void rollbackAfterFlushRestoresPlacementAndStickers() {
		attachAll();
		var before = owned();
		assertThatThrownBy(() -> new TransactionTemplate(transactions).executeWithoutResult(status -> {
			service.updatePlacements(userId, layout(sofa));
			assertThat(current(sofa).stickerAttached()).isTrue();
			throw new IllegalStateException("failure after flush");
		})).isInstanceOf(IllegalStateException.class);
		assertThat(owned()).isEqualTo(before);
	}

	@Test
	void legacyApiCannotBypassCountRuleAndCanMovePurchasedEssentialFurniture() throws Exception {
		String install = "{\"placed\":true,\"placementStatus\":\"FLOOR\",\"placementDirection\":\"FRONT_LEFT\",\"positionX\":1,\"positionY\":500}";
		mvc.perform(auth(patch("/api/v1/furnitures/" + sofa).contentType(APPLICATION_JSON).content(install)))
				.andExpect(status().isConflict()).andExpect(jsonPath("$.code").value("FURNITURE_004"));
		service.updatePlacements(userId, layout(sofa));
		mvc.perform(auth(patch("/api/v1/furnitures/" + sofa).contentType(APPLICATION_JSON).content(install)))
				.andExpect(status().isOk()).andExpect(jsonPath("$.data.positionY").value(500));
		mvc.perform(auth(patch("/api/v1/furnitures/" + sofa).contentType(APPLICATION_JSON).content("{\"placed\":false}")))
				.andExpect(status().isConflict()).andExpect(jsonPath("$.code").value("FURNITURE_003"));
		mvc.perform(auth(patch("/api/v1/furnitures/" + starter.get(FurnitureType.SOFA)).contentType(APPLICATION_JSON).content(install)))
				.andExpect(status().isConflict()).andExpect(jsonPath("$.code").value("FURNITURE_004"));
	}

	@Test
	void replacementPreservesRemovedStickerAndAllowsAnotherRemoval() {
		attachAll();
		service.updatePlacements(userId, layout(sofa));
		assertThat(stickers.remove(userId, sofa).stickers().count()).isEqualTo(3);
		service.updatePlacements(userId, layout(pinkSofa));
		assertThat(current(pinkSofa).stickerAttached()).isFalse();
		assertThat(stickers.remove(userId, starter.get(FurnitureType.DINING_TABLE)).stickers().count()).isEqualTo(2);
		assertThatThrownBy(() -> stickers.remove(userId, pinkSofa))
				.isInstanceOfSatisfying(BusinessException.class, e -> assertThat(e.getErrorCode().getCode()).isEqualTo("ROOM_003"));
		assertThatThrownBy(() -> stickers.remove(userId, sofa))
				.isInstanceOfSatisfying(BusinessException.class, e -> assertThat(e.getErrorCode().getCode()).isEqualTo("ROOM_001"));
	}

	@Test
	void concurrentSavesCommitCompleteLayoutsWithLastWriterWinning() throws Exception {
		attachAll();
		var locked = new CountDownLatch(1);
		var release = new CountDownLatch(1);
		var secondStarted = new CountDownLatch(1);
		try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
			var first = executor.submit(() -> new TransactionTemplate(transactions).executeWithoutResult(status -> {
				service.updatePlacements(userId, layout(sofa));
				locked.countDown();
				await(release);
			}));
			try {
				assertThat(locked.await(15, TimeUnit.SECONDS)).isTrue();
				var second = executor.submit(() -> {
					secondStarted.countDown();
					return service.updatePlacements(userId, layout(pinkSofa));
				});
				assertThat(secondStarted.await(5, TimeUnit.SECONDS)).isTrue();
				assertThat(second.isDone()).isFalse();
				release.countDown();
				first.get(15, TimeUnit.SECONDS);
				second.get(15, TimeUnit.SECONDS);
			} finally {
				release.countDown();
			}
		}
		assertThat(current(pinkSofa).placed()).isTrue();
		assertThat(current(pinkSofa).stickerAttached()).isTrue();
		assertThat(current(sofa).placed()).isFalse();
		assertThat(owned()).filteredOn(UserFurnitureResponse::placed).hasSize(4);
	}

	@Test
	void concurrentReplacementAndRemovalNeverLoseOrDuplicateSticker() throws Exception {
		attachAll();
		var start = new CountDownLatch(1);
		try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
			var save = executor.submit(() -> { await(start); return service.updatePlacements(userId, layout(sofa)); });
			var remove = executor.submit(() -> {
				await(start);
				try { stickers.remove(userId, starter.get(FurnitureType.SOFA)); return "SUCCESS"; }
				catch (BusinessException e) { return e.getErrorCode().getCode(); }
			});
			start.countDown();
			save.get(15, TimeUnit.SECONDS);
			String result = remove.get(15, TimeUnit.SECONDS);
			assertThat(result).isIn("SUCCESS", "ROOM_001");
			assertThat(current(sofa).stickerAttached()).isEqualTo(result.equals("ROOM_001"));
		}
		assertThat(current(starter.get(FurnitureType.SOFA)).stickerAttached()).isFalse();
		assertThat(owned()).filteredOn(UserFurnitureResponse::placed).hasSize(4);
	}

	private long acquire(long owner, String assetKey) {
		jdbc.sql("INSERT INTO user_furnitures (user_id, item_id) SELECT :user, id FROM items WHERE asset_key = :asset")
				.param("user", owner).param("asset", assetKey).update();
		return jdbc.sql("SELECT uf.id FROM user_furnitures uf JOIN items i ON i.id = uf.item_id WHERE uf.user_id = :user AND i.asset_key = :asset")
				.param("user", owner).param("asset", assetKey).query(Long.class).single();
	}

	private Placement entry(long id) {
		return new Placement(id, FLOOR, FRONT_LEFT, new BigDecimal("327.000"), new BigDecimal("586.000"), -2);
	}

	private FurniturePlacementsUpdateRequest layout(long sofaId) {
		return new FurniturePlacementsUpdateRequest(List.of(entry(starter.get(FurnitureType.DINING_TABLE)), entry(starter.get(FurnitureType.TV)),
				entry(sofaId), entry(starter.get(FurnitureType.COFFEE_TABLE))));
	}

	private List<UserFurnitureResponse> owned() { return service.getFurnitures(userId, null); }
	private UserFurnitureResponse current(long id) { return owned().stream().filter(f -> f.userFurnitureId() == id).findFirst().orElseThrow(); }
	private MockHttpServletRequestBuilder auth(MockHttpServletRequestBuilder request) {
		return request.header("Authorization", "Bearer " + tokens.generateAccessToken(userId));
	}
	private void attachAll() {
		jdbc.sql("UPDATE user_furnitures SET sticker_attached = TRUE WHERE user_id = :user AND placement_status IS NOT NULL")
				.param("user", userId).update();
	}
	private void assertRejected(FurniturePlacementsUpdateRequest request, int status, String code) throws Exception {
		mvc.perform(auth(put("/api/v1/furnitures/placements").contentType(APPLICATION_JSON).content(json.writeValueAsString(request))))
				.andExpect(status().is(status)).andExpect(jsonPath("$.code").value(code));
	}
	private void assertInvalidBody(String body, String code) throws Exception {
		mvc.perform(auth(put("/api/v1/furnitures/placements").contentType(APPLICATION_JSON).content(body)))
				.andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value(code));
	}
	private Map<String, String> entryFields() {
		return new LinkedHashMap<>(Map.of("userFurnitureId", String.valueOf(sofa), "placementStatus", "\"FLOOR\"",
				"placementDirection", "\"FRONT_LEFT\"", "positionX", "1", "positionY", "500", "layer", "-2"));
	}
	private String bodyOf(Map<String, String> fields) {
		return "{\"placements\":[{" + fields.entrySet().stream().map(e -> "\"" + e.getKey() + "\":" + e.getValue())
				.collect(Collectors.joining(",")) + "}]}";
	}
	private static void await(CountDownLatch latch) {
		try { if (!latch.await(15, TimeUnit.SECONDS)) throw new IllegalStateException("latch timeout"); }
		catch (InterruptedException e) { Thread.currentThread().interrupt(); throw new IllegalStateException(e); }
	}
}
