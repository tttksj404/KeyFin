package com.finset.key_fin.room;

import com.finset.key_fin.auth.dto.request.SignupRequest;
import com.finset.key_fin.auth.jwt.JwtTokenProvider;
import com.finset.key_fin.auth.service.AuthService;
import com.finset.key_fin.budget.dto.request.BudgetConfirmRequest;
import com.finset.key_fin.budget.service.BudgetService;
import com.finset.key_fin.budget.service.EnvelopeBalanceService;
import com.finset.key_fin.furniture.dto.request.FurniturePlacementUpdateRequest;
import com.finset.key_fin.furniture.dto.request.FurniturePlacementsUpdateRequest;
import com.finset.key_fin.furniture.dto.request.FurniturePlacementsUpdateRequest.Placement;
import com.finset.key_fin.furniture.entity.FurnitureType;
import com.finset.key_fin.furniture.entity.FurniturePlacementDirection;
import com.finset.key_fin.furniture.entity.FurniturePlacementStatus;
import com.finset.key_fin.furniture.service.DefaultFurnitureService;
import com.finset.key_fin.furniture.service.FurnitureService;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.room.service.RoomService;
import com.finset.key_fin.room.service.RoomStickerService;
import com.finset.key_fin.support.SpringIntegrationTestSupport;
import com.finset.key_fin.transaction.dto.request.BulkTransactionClassificationRequest;
import com.finset.key_fin.transaction.dto.request.TransactionClassificationRequest;
import com.finset.key_fin.transaction.entity.ExcludeTag;
import com.finset.key_fin.transaction.repository.TransactionRepository;
import com.finset.key_fin.transaction.service.TransactionService;
import com.finset.key_fin.transaction.service.TransactionSyncWriter;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.repository.UserRepository;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.Primary;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.*;
import static org.springframework.http.MediaType.APPLICATION_JSON;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@Timeout(90)
class RoomStickersIntegrationTest extends SpringIntegrationTestSupport {
	private static final Instant NOW = Instant.parse("2026-09-18T03:00:00Z");
	@Autowired private UserRepository users;
	@Autowired private JdbcClient jdbc;
	@Autowired private RoomService rooms;
	@Autowired private RoomStickerService stickers;
	@Autowired private DefaultFurnitureService defaults;
	@Autowired private FurnitureService furnitureService;
	@Autowired private AuthService authService;
	@Autowired private BudgetService budgetService;
	@Autowired private EnvelopeBalanceService balances;
	@Autowired private TransactionService transactions;
	@Autowired private TransactionRepository transactionRepository;
	@Autowired private TransactionSyncWriter syncWriter;
	@Autowired private PlatformTransactionManager transactionManager;
	@Autowired private MockMvc mvc;
	@Autowired private JwtTokenProvider tokens;
	private final List<Long> testUsers = new ArrayList<>();
	private final List<Long> testItems = new ArrayList<>();
	private long userId;

	@BeforeEach
	void setUp() {
		testClock.set(NOW);
		userId = createUser();
	}

	@AfterEach
	void cleanUp() {
		for (long id : testUsers) {
			jdbc.sql("DELETE FROM notifications WHERE user_id = :id").param("id", id).update();
			jdbc.sql("DELETE s FROM budget_alert_states s JOIN budgets b ON b.id = s.budget_id WHERE b.user_id = :id").param("id", id).update();
			jdbc.sql("DELETE FROM transactions WHERE user_id = :id").param("id", id).update();
			jdbc.sql("DELETE be FROM budget_envelopes be JOIN budgets b ON b.id = be.budget_id WHERE b.user_id = :id").param("id", id).update();
			for (String table : List.of("budgets", "user_furnitures", "fin_coin", "user_profiles", "user_settings")) {
				jdbc.sql("DELETE FROM " + table + " WHERE user_id = :id").param("id", id).update();
			}
			users.deleteById(id);
		}
		for (long id : testItems) jdbc.sql("DELETE FROM items WHERE id = :id").param("id", id).update();
	}

	@Test
	void signupStartsWithoutStickersAndRoomDoesNotCreateBudgetOrAttendance() throws Exception {
		long signedUp = authService.signup(new SignupRequest(UUID.randomUUID() + "@room.test", "Passw0rd!", "방테스터")).userId();
		testUsers.add(signedUp);
		var supplied = furnitureService.getFurnitures(signedUp, null);
		assertThat(supplied).hasSize(4).allSatisfy(f -> assertThat(f.stickerAttached()).isFalse());
		mvc.perform(auth(get("/api/v1/room"), signedUp)).andExpect(status().isOk())
				.andExpect(jsonPath("$.data.coin.balance").value(0))
				.andExpect(jsonPath("$.data.attendance.checkedToday").value(false))
				.andExpect(jsonPath("$.data.stickers.count").value(0))
				.andExpect(jsonPath("$.data.stickers.total").value(4))
				.andExpect(jsonPath("$.data.overEnvelopes").isEmpty())
				.andExpect(jsonPath("$.data.stickers.removableToday").value(false));
		assertThat(countFor("budgets", signedUp)).isZero();
		assertThat(countFor("fin_coin", signedUp)).isZero();
	}

	@Test
	void existingOverrunAttachesOnceAndMatchesIndividualRoomStates() throws Exception {
		budget("202609", "CONFIRMED", 1000);
		spend("2026-09-18", 1001, "CONFIRMED", 101);
		var first = rooms.getRoom(userId);
		assertThat(first.stickers().count()).isEqualTo(4);
		assertThat(first.furnitures()).allSatisfy(f -> assertThat(f.stickerAttached()).isTrue());
		long sofa = target("SOFA");
		mvc.perform(auth(removal(sofa), userId)).andExpect(status().isOk())
				.andExpect(jsonPath("$.data.userFurnitureId").value(sofa))
				.andExpect(jsonPath("$.data.stickerAttached").value(false))
				.andExpect(jsonPath("$.data.stickers.count").value(3))
				.andExpect(jsonPath("$.data.stickers.removableToday").value(true));
		assertThat(rooms.getRoom(userId).stickers().count()).isEqualTo(3);
		assertThat(countFor("budget_sticker_applications", userId)).isEqualTo(1);
	}

	@Test
	void equalityAndOneEnvelopeOverrunDoNotExceedTotalBudget() {
		long budget = budget("202609", "CONFIRMED", 1000);
		spend("2026-09-18", 1000, "CONFIRMED", 101);
		assertThat(rooms.getRoom(userId).overEnvelopes()).isEmpty();
		assertThat(rooms.getRoom(userId).stickers().count()).isZero();
		jdbc.sql("UPDATE budget_envelopes SET confirmed_amount = CASE envelope_id WHEN 1 THEN 0 WHEN 2 THEN 1000 ELSE 0 END WHERE budget_id = :id")
				.param("id", budget).update();
		assertThat(rooms.getRoom(userId).overEnvelopes()).containsExactly(1);
		assertThat(rooms.getRoom(userId).stickers().count()).isZero();
	}

	@Test
	void categoryEffectsAndStickersFollowRefundReclassificationAndCancellation() throws Exception {
		budget("202609", "CONFIRMED", 1000);
		spend("2026-09-18", 1001, "AUTO", 101);
		long leisure = spend("2026-09-18", 1, "CONFIRMED", 401);
		mvc.perform(auth(get("/api/v1/room"), userId)).andExpect(status().isOk())
				.andExpect(jsonPath("$.data.overEnvelopes.length()").value(2))
				.andExpect(jsonPath("$.data.overEnvelopes[0]").value(1))
				.andExpect(jsonPath("$.data.overEnvelopes[1]").value(4));
		stickers.remove(userId, target("DINING_TABLE"));
		assertThat(rooms.getRoom(userId).overEnvelopes()).containsExactly(1, 4);
		long refund = spend("2026-09-18", 1, "AUTO", 101);
		jdbc.sql("UPDATE transactions SET tx_type = 'DEPOSIT', exclude_tag = 'RESTORE' WHERE id = :id").param("id", refund).update();
		assertThat(rooms.getRoom(userId).overEnvelopes()).containsExactly(4);
		transactions.classifyTransaction(userId, leisure, new TransactionClassificationRequest(201, null, null));
		assertThat(rooms.getRoom(userId).overEnvelopes()).containsExactly(2);
		assertThat(rooms.getRoom(userId).stickers().count()).isEqualTo(3);
		jdbc.sql("UPDATE transactions SET status = 'CANCELED' WHERE id = :id").param("id", leisure).update();
		assertThat(rooms.getRoom(userId).overEnvelopes()).isEmpty();
		assertThat(rooms.getRoom(userId).stickers().count()).isZero();
		assertThat(rooms.getRoom(userId).furnitures()).allSatisfy(f -> assertThat(f.stickerAttached()).isFalse());
	}

	@Test
	void categoryEffectsClearAtAnchorBoundaryAndWaitForNextConfirmation() {
		jdbc.sql("INSERT INTO user_settings (user_id, budget_anchor_day) VALUES (:user, 23)").param("user", userId).update();
		budget("202608", "CONFIRMED", 1000);
		spend("2026-09-22", 1001, "CONFIRMED", 101);
		testClock.set(Instant.parse("2026-09-22T14:59:59Z"));
		assertThat(rooms.getRoom(userId).overEnvelopes()).containsExactly(1);
		testClock.set(Instant.parse("2026-09-22T15:00:00Z"));
		assertThat(rooms.getRoom(userId).overEnvelopes()).isEmpty();
		long next = budget("202609", "PROPOSED", 1000);
		spend("2026-09-23", 1, "CONFIRMED", 401);
		assertThat(rooms.getRoom(userId).overEnvelopes()).isEmpty();
		budgetService.confirm(userId, next, confirmation(1000));
		assertThat(rooms.getRoom(userId).overEnvelopes()).containsExactly(4);
	}

	@Test
	void ignoresUnconfirmedPendingCanceledAndExcludedSpending() {
		long budget = budget("202609", "PROPOSED", 1000);
		long tx = spend("2026-09-18", 2000, "CONFIRMED", 101);
		assertThat(rooms.getRoom(userId).stickers().count()).isZero();
		jdbc.sql("UPDATE budgets SET status = 'CONFIRMED' WHERE id = :id").param("id", budget).update();
		jdbc.sql("UPDATE transactions SET confirm_status = 'PENDING' WHERE id = :id").param("id", tx).update();
		assertThat(rooms.getRoom(userId).stickers().count()).isZero();
		jdbc.sql("UPDATE transactions SET confirm_status = 'CONFIRMED', status = 'CANCELED' WHERE id = :id").param("id", tx).update();
		assertThat(rooms.getRoom(userId).stickers().count()).isZero();
		jdbc.sql("UPDATE transactions SET status = 'NORMAL', exclude_tag = 'EMERGENCY' WHERE id = :id").param("id", tx).update();
		assertThat(rooms.getRoom(userId).stickers().count()).isZero();
	}

	@Test
	void recoveringBudgetAllowsRepeatedReattachmentInTheSamePeriod() {
		budget("202609", "CONFIRMED", 1000);
		long tx = spend("2026-09-18", 2000, "CONFIRMED", 101);
		rooms.getRoom(userId);
		stickers.remove(userId, target("DINING_TABLE"));
		for (int cycle = 0; cycle < 2; cycle++) {
			transactions.classifyTransaction(userId, tx, new TransactionClassificationRequest(null, ExcludeTag.EMERGENCY, null));
			assertThat(attachedCount()).isZero();
			assertThat(countFor("budget_sticker_applications", userId)).isZero();
			assertBusinessCode(() -> stickers.remove(userId, target("SOFA")), "ROOM_003");
			transactions.classifyTransaction(userId, tx, new TransactionClassificationRequest(101, null, null));
			assertThat(attachedCount()).isEqualTo(4);
			assertThat(rooms.getRoom(userId).stickers().removableToday()).isTrue();
			assertThat(countFor("budget_sticker_applications", userId)).isEqualTo(1);
			stickers.remove(userId, target("DINING_TABLE"));
			assertThat(rooms.getRoom(userId).stickers().count()).isEqualTo(3);
		}
		assertThat(countFor("room_sticker_states", userId)).isZero();
	}

	@ParameterizedTest
	@ValueSource(longs = {0, 1000, 1001})
	void cancellationSyncRemovesPlacedAndStoredStickersOnlyAfterTotalBudgetRecovers(long remainingSpending) throws Exception {
		defaults.provision(userId);
		long fridge = acquireCatalog("refrigerator_black");
		furnitureService.updatePlacement(userId, fridge, moved());
		budget("202609", "CONFIRMED", 1000);
		if (remainingSpending > 0) spend("2026-09-18", remainingSpending, "CONFIRMED", 101);
		long tx = spend("2026-09-18", 2000, "CONFIRMED", 101);
		assertThat(rooms.getRoom(userId).stickers().count()).isEqualTo(5);
		furnitureService.updatePlacement(userId, fridge, new FurniturePlacementUpdateRequest(false, null, null, null, null, null));

		var canceled = transactionRepository.findById(tx).orElseThrow();
		canceled.cancel();
		syncWriter.save(userId, List.of(), List.of(), Map.of(tx, canceled), Map.of(1, 2_000L));

		boolean stillExceeded = remainingSpending > 1000;
		assertThat(balances.getRemaining(userId, "202609", 1)).contains(1000 - remainingSpending);
		// Check committed state before a room read can repair it.
		assertThat(attachedCount()).isEqualTo(stillExceeded ? 5 : 0);
		assertThat(furnitureService.getFurnitures(userId, null))
				.allSatisfy(f -> assertThat(f.stickerAttached()).isEqualTo(stillExceeded));
		mvc.perform(auth(get("/api/v1/room"), userId)).andExpect(status().isOk())
				.andExpect(jsonPath("$.data.stickers.count").value(stillExceeded ? 4 : 0))
				.andExpect(jsonPath("$.data.stickers.total").value(4))
				.andExpect(jsonPath("$.data.stickers.removableToday").value(stillExceeded));
		furnitureService.updatePlacement(userId, fridge, moved());
		assertThat(rooms.getRoom(userId).stickers().count()).isEqualTo(stillExceeded ? 5 : 0);
		syncWriter.save(userId, List.of(), List.of(), Map.of(tx, canceled), Map.of(1, 2_000L));
		assertThat(attachedCount()).isEqualTo(stillExceeded ? 5 : 0);
		assertThat(countFor("budget_sticker_applications", userId)).isEqualTo(stillExceeded ? 1 : 0);
	}

	@Test
	void paymentAfterCancellationReattachesToAllCurrentlyPlacedFurnitureBeforeRoomIsRead() throws Exception {
		budget("202609", "CONFIRMED", 1000);
		long tx = spend("2026-09-18", 2000, "CONFIRMED", 101);
		assertThat(rooms.getRoom(userId).stickers().count()).isEqualTo(4);
		stickers.remove(userId, target("DINING_TABLE"));
		var canceled = transactionRepository.findById(tx).orElseThrow();
		canceled.cancel();
		syncWriter.save(userId, List.of(), List.of(), Map.of(tx, canceled), Map.of(1, 2_000L));
		assertThat(attachedCount()).isZero();
		assertThat(countFor("budget_sticker_applications", userId)).isZero();

		// The next overrun also includes furniture installed after the earlier application.
		long fridge = acquireCatalog("refrigerator_black");
		furnitureService.updatePlacement(userId, fridge, moved());
		long nextTx = spend("2026-09-18", 2000, "PENDING", null);
		var payment = transactionRepository.findById(nextTx).orElseThrow();
		payment.confirmSubcategory(101);
		syncWriter.save(userId, List.of(), List.of(), Map.of(nextTx, payment), Map.of());
		assertThat(attachedCount()).isEqualTo(5);
		assertThat(countFor("budget_sticker_applications", userId)).isEqualTo(1);
		mvc.perform(auth(get("/api/v1/room"), userId)).andExpect(status().isOk())
				.andExpect(jsonPath("$.data.stickers.count").value(5))
				.andExpect(jsonPath("$.data.stickers.total").value(5));
		assertThat(rooms.getRoom(userId).furnitures()).allSatisfy(f -> assertThat(f.stickerAttached()).isTrue());
	}

	@Test
	void nextExceededBudgetStickersCanBeRemovedImmediatelyAfterEarlierRemoval() {
		budget("202609", "CONFIRMED", 1000);
		spend("2026-09-18", 2000, "CONFIRMED", 101);
		rooms.getRoom(userId);
		stickers.remove(userId, target("DINING_TABLE"));
		testClock.set(Instant.parse("2026-10-01T03:00:00Z"));
		long next = budget("202610", "PROPOSED", 1000);
		assertThat(rooms.getRoom(userId).stickers().count()).isEqualTo(3);
		stickers.remove(userId, target("SOFA"));
		assertThat(rooms.getRoom(userId).stickers().count()).isEqualTo(2);
		spend("2026-10-01", 2000, "CONFIRMED", 101);
		budgetService.confirm(userId, next, confirmation(1000));
		assertThat(rooms.getRoom(userId).stickers().count()).isEqualTo(4);
		assertThat(rooms.getRoom(userId).stickers().removableToday()).isTrue();
		assertThat(stickers.remove(userId, target("TV")).stickers().count()).isEqualTo(3);
		assertThat(countFor("budget_sticker_applications", userId)).isEqualTo(2);
	}

	@Test
	void usesAnchorDayAndDoesNotApplyEndedBudget() {
		jdbc.sql("INSERT INTO user_settings (user_id, budget_anchor_day) VALUES (:user, 23)").param("user", userId).update();
		budget("202608", "CONFIRMED", 1000);
		spend("2026-08-23", 2000, "CONFIRMED", 101);
		assertThat(rooms.getRoom(userId).stickers().count()).isEqualTo(4);
		userId = createUser();
		budget("202608", "CONFIRMED", 1000);
		long oldTransaction = spend("2026-08-31", 2000, "PENDING", null);
		transactions.classifyTransaction(userId, oldTransaction, new TransactionClassificationRequest(101, null, null));
		assertThat(rooms.getRoom(userId).stickers().count()).isZero();
		assertThat(countFor("budget_sticker_applications", userId)).isZero();
	}

	@Test
	void consecutiveRemovalsWorkBothBeforeAndAfterKoreanMidnight() {
		budget("202609", "CONFIRMED", 1000);
		spend("2026-09-18", 2000, "CONFIRMED", 101);
		rooms.getRoom(userId);
		testClock.set(Instant.parse("2026-09-18T14:59:59Z"));
		stickers.remove(userId, target("DINING_TABLE"));
		assertThat(stickers.remove(userId, target("SOFA")).stickers().count()).isEqualTo(2);
		testClock.set(Instant.parse("2026-09-18T15:00:00Z"));
		assertThat(stickers.remove(userId, target("TV")).stickers().count()).isEqualTo(1);
		var last = stickers.remove(userId, target("COFFEE_TABLE")).stickers();
		assertThat(last.count()).isZero();
		assertThat(last.removableToday()).isFalse();
	}

	@Test
	void legacyRemovalDateDoesNotBlockOrChangeAfterFurtherRemovals() throws Exception {
		budget("202609", "CONFIRMED", 1000);
		spend("2026-09-18", 2000, "CONFIRMED", 101);
		rooms.getRoom(userId);
		jdbc.sql("INSERT INTO room_sticker_states (user_id, last_removed_date) VALUES (:user, '2026-09-18')")
				.param("user", userId).update();
		assertThat(rooms.getRoom(userId).stickers().removableToday()).isTrue();
		mvc.perform(auth(removal(target("SOFA")), userId)).andExpect(status().isOk())
				.andExpect(jsonPath("$.data.stickers.count").value(3))
				.andExpect(jsonPath("$.data.stickers.removableToday").value(true));
		mvc.perform(auth(removal(target("TV")), userId)).andExpect(status().isOk());
		mvc.perform(auth(removal(target("SOFA")), userId)).andExpect(status().isConflict())
				.andExpect(jsonPath("$.code").value("ROOM_003"));
		testClock.set(NOW.plusSeconds(86400));
		stickers.remove(userId, target("DINING_TABLE"));
		var last = stickers.remove(userId, target("COFFEE_TABLE")).stickers();
		assertThat(last.count()).isZero();
		assertThat(last.removableToday()).isFalse();
		assertThat(jdbc.sql("SELECT last_removed_date FROM room_sticker_states WHERE user_id = :user")
				.param("user", userId).query(LocalDate.class).single()).isEqualTo(LocalDate.parse("2026-09-18"));
	}

	@Test
	void validatesOwnershipPlacementAndMissingSticker() throws Exception {
		defaults.provision(userId);
		long ordinary = ordinaryFurniture();
		mvc.perform(auth(removal(ordinary), userId)).andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("ROOM_001"));
		long other = createUser();
		long otherFurniture = defaults.provision(other).getFirst().getId();
		mvc.perform(auth(removal(otherFurniture), userId)).andExpect(status().isNotFound());
		mvc.perform(auth(removal(Long.MAX_VALUE), userId)).andExpect(status().isNotFound());
		mvc.perform(auth(removal(target("SOFA")), userId)).andExpect(status().isConflict())
				.andExpect(jsonPath("$.code").value("ROOM_003"));
		mvc.perform(auth(post("/api/v1/room/stickers/removals").contentType(APPLICATION_JSON).content("{}"), userId))
				.andExpect(status().isBadRequest());
		mvc.perform(removal(target("SOFA"))).andExpect(status().isUnauthorized());
		assertThat(countFor("room_sticker_states", userId)).isZero();
	}

	private long ordinaryFurniture() {
		String asset = UUID.randomUUID().toString();
		jdbc.sql("INSERT INTO items (item_category, slot_type, name, price, asset_key, is_active) VALUES ('FURNITURE', 'FLOOR', '일반 가구', 10, :asset, TRUE)")
				.param("asset", asset).update();
		long item = jdbc.sql("SELECT id FROM items WHERE asset_key = :asset").param("asset", asset).query(Long.class).single();
		testItems.add(item);
		jdbc.sql("INSERT INTO user_furnitures (user_id, item_id) VALUES (:user, :item)").param("user", userId).param("item", item).update();
		return jdbc.sql("SELECT id FROM user_furnitures WHERE user_id = :user AND item_id = :item")
				.param("user", userId).param("item", item).query(Long.class).single();
	}

	@Test
	void firstOverrunStampsEveryFloorKindButNotWallsStorageOrLaterInstallations() throws Exception {
		defaults.provision(userId);
		var floorIds = List.of("refrigerator_black", "refrigerator_pink", "bed_pink", "decor_checker_rug",
				"plant_monstera_terracotta", "decor_arc_floor_lamp").stream().map(this::acquireCatalog).toList();
		floorIds.forEach(id -> furnitureService.updatePlacement(userId, id, moved()));
		long wall = acquireCatalog("decor_round_wall_clock");
		furnitureService.updatePlacement(userId, wall, new FurniturePlacementUpdateRequest(true,
				FurniturePlacementStatus.LEFT_WALL, FurniturePlacementDirection.FRONT_RIGHT,
				BigDecimal.TEN, BigDecimal.TEN, 0));
		long stored = acquireCatalog("desk_black");
		budget("202609", "CONFIRMED", 1000);
		spend("2026-09-18", 2000, "CONFIRMED", 101);
		var first = rooms.getRoom(userId);
		assertThat(first.stickers().total()).isEqualTo(10);
		assertThat(first.stickers().count()).isEqualTo(10);
		assertThat(first.furnitures()).filteredOn(f -> f.placementStatus() == FurniturePlacementStatus.FLOOR)
				.allSatisfy(f -> assertThat(f.stickerAttached()).isTrue());
		assertThat(furnitureService.getFurnitures(userId, null)).filteredOn(f -> f.userFurnitureId() == wall || f.userFurnitureId() == stored)
				.allSatisfy(f -> assertThat(f.stickerAttached()).isFalse());
		mvc.perform(auth(removal(wall), userId)).andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value("ROOM_001"));
		furnitureService.updatePlacement(userId, stored, moved());
		assertThat(rooms.getRoom(userId).stickers().total()).isEqualTo(11);
		assertThat(rooms.getRoom(userId).stickers().count()).isEqualTo(10);
		mvc.perform(auth(removal(stored), userId)).andExpect(status().isConflict()).andExpect(jsonPath("$.code").value("ROOM_003"));
		mvc.perform(auth(removal(floorIds.getFirst()), userId)).andExpect(status().isOk())
				.andExpect(jsonPath("$.data.stickers.count").value(9)).andExpect(jsonPath("$.data.stickers.total").value(11));
		assertThat(rooms.getRoom(userId).stickers().count()).isEqualTo(9);
		testClock.set(Instant.parse("2026-10-01T03:00:00Z"));
		budget("202610", "CONFIRMED", 1000);
		spend("2026-10-01", 2000, "CONFIRMED", 101);
		assertThat(rooms.getRoom(userId).stickers().count()).isEqualTo(11);
	}

	@Test
	void ordinaryStickerSurvivesSingleAndBatchStorage() {
		defaults.provision(userId);
		long fridge = acquireCatalog("refrigerator_black");
		furnitureService.updatePlacement(userId, fridge, moved());
		budget("202609", "CONFIRMED", 1000);
		spend("2026-09-18", 2000, "CONFIRMED", 101);
		assertThat(rooms.getRoom(userId).stickers().count()).isEqualTo(5);
		assertThat(furnitureService.updatePlacement(userId, fridge, moved()).stickerAttached()).isTrue();
		var stored = furnitureService.updatePlacement(userId, fridge, new FurniturePlacementUpdateRequest(false, null, null, null, null, null));
		assertThat(stored.stickerAttached()).isTrue();
		assertThat(rooms.getRoom(userId).stickers().total()).isEqualTo(4);
		assertThat(rooms.getRoom(userId).stickers().count()).isEqualTo(4);
		assertBusinessCode(() -> stickers.remove(userId, fridge), "ROOM_001");
		assertThat(countFor("room_sticker_states", userId)).isZero();
		assertThat(furnitureService.updatePlacement(userId, fridge, moved()).stickerAttached()).isTrue();
		var full = new FurniturePlacementsUpdateRequest(furnitureService.getPlacedFurnitures(userId).stream()
				.map(f -> new Placement(f.userFurnitureId(), f.placementStatus(), f.placementDirection(), f.positionX(), f.positionY(), f.layer())).toList());
		furnitureService.updatePlacements(userId, full);
		assertThat(rooms.getRoom(userId).stickers().count()).isEqualTo(5);
		var withoutFridge = new FurniturePlacementsUpdateRequest(full.placements().stream().filter(f -> f.userFurnitureId() != fridge).toList());
		assertThat(furnitureService.updatePlacements(userId, withoutFridge)).filteredOn(f -> f.userFurnitureId() == fridge)
				.singleElement().satisfies(f -> { assertThat(f.placed()).isFalse(); assertThat(f.stickerAttached()).isTrue(); });
		assertThat(rooms.getRoom(userId).stickers().count()).isEqualTo(4);
		furnitureService.updatePlacements(userId, full);
		assertThat(rooms.getRoom(userId).stickers().count()).isEqualTo(5);
		stickers.remove(userId, fridge);
		furnitureService.updatePlacements(userId, withoutFridge);
		furnitureService.updatePlacements(userId, full);
		assertThat(rooms.getRoom(userId).stickers().count()).isEqualTo(4);
		assertThat(rooms.getRoom(userId).stickers().removableToday()).isTrue();
	}

	private long acquireCatalog(String assetKey) {
		jdbc.sql("INSERT INTO user_furnitures (user_id, item_id) SELECT :user, id FROM items WHERE asset_key = :asset")
				.param("user", userId).param("asset", assetKey).update();
		return jdbc.sql("SELECT uf.id FROM user_furnitures uf JOIN items i ON i.id = uf.item_id WHERE uf.user_id = :user AND i.asset_key = :asset")
				.param("user", userId).param("asset", assetKey).query(Long.class).single();
	}

	@Test
	void defaultFurnitureCannotBeUnplacedButMovingKeepsSticker() throws Exception {
		budget("202609", "CONFIRMED", 1000);
		spend("2026-09-18", 2000, "CONFIRMED", 101);
		rooms.getRoom(userId);
		long sofa = target("SOFA");
		mvc.perform(auth(patch("/api/v1/furnitures/" + sofa).contentType(APPLICATION_JSON).content("{\"placed\":false}"), userId))
				.andExpect(status().isConflict()).andExpect(jsonPath("$.code").value("FURNITURE_003"));
		assertThat(furnitureService.updatePlacement(userId, sofa, moved()).stickerAttached()).isTrue();
		stickers.remove(userId, sofa);
		assertBusinessCode(() -> furnitureService.updatePlacement(userId, sofa,
				new FurniturePlacementUpdateRequest(false, null, null, null, null, null)), "FURNITURE_003");
	}

	@Test
	void replacementReceivesFutureBudgetStickersWithoutReinstallingStarter() {
		budget("202609", "CONFIRMED", 1000);
		spend("2026-09-18", 2000, "CONFIRMED", 101);
		rooms.getRoom(userId);
		long oldSofa = target("SOFA");
		jdbc.sql("INSERT INTO user_furnitures (user_id, item_id) SELECT :user, id FROM items WHERE asset_key = 'sofa_black'")
				.param("user", userId).update();
		long newSofa = jdbc.sql("SELECT uf.id FROM user_furnitures uf JOIN items i ON i.id = uf.item_id WHERE uf.user_id = :user AND i.asset_key = 'sofa_black'")
				.param("user", userId).query(Long.class).single();
		var request = new FurniturePlacementsUpdateRequest(furnitureService.getPlacedFurnitures(userId).stream()
				.map(f -> new Placement(f.furnitureType() == FurnitureType.SOFA ? newSofa : f.userFurnitureId(),
						f.placementStatus(), f.placementDirection(), f.positionX(), f.positionY(), f.layer())).toList());
		furnitureService.updatePlacements(userId, request);
		assertThat(stickers.remove(userId, newSofa).stickers().count()).isEqualTo(3);
		furnitureService.updatePlacements(userId, request);
		assertThat(rooms.getRoom(userId).stickers().count()).isEqualTo(3);
		assertThat(countFor("budget_sticker_applications", userId)).isEqualTo(1);
		testClock.set(Instant.parse("2026-10-01T03:00:00Z"));
		budget("202610", "CONFIRMED", 1000);
		spend("2026-10-01", 2000, "CONFIRMED", 101);
		var next = rooms.getRoom(userId);
		assertThat(next.stickers().count()).isEqualTo(4);
		assertThat(next.furnitures()).extracting(f -> f.userFurnitureId()).contains(newSofa).doesNotContain(oldSofa);
		assertThat(countFor("budget_sticker_applications", userId)).isEqualTo(2);
		assertThat(jdbc.sql("SELECT sticker_attached FROM user_furnitures WHERE id = :id").param("id", oldSofa).query(Boolean.class).single()).isFalse();
	}

	@Test
	void classificationAndSyncWriterApplyOverrunBeforeRoomIsRead() {
		budget("202609", "CONFIRMED", 1000);
		long tx = spend("2026-09-18", 2000, "PENDING", null);
		transactions.classifyTransaction(userId, tx, new TransactionClassificationRequest(101, null, null));
		assertThat(attachedCount()).isEqualTo(4);
		assertThat(countFor("budget_sticker_applications", userId)).isEqualTo(1);
		// A separate period exercises the sync writer with a detached, newly classified transaction.
		testClock.set(Instant.parse("2026-10-01T03:00:00Z"));
		budget("202610", "CONFIRMED", 1000);
		long nextTx = spend("2026-10-01", 2000, "PENDING", null);
		var changed = transactionRepository.findById(nextTx).orElseThrow();
		changed.confirmSubcategory(101);
		syncWriter.save(userId, List.of(), List.of(), Map.of(nextTx, changed), Map.of());
		assertThat(countFor("budget_sticker_applications", userId)).isEqualTo(2);
	}

	@Test
	void bulkClassificationEvaluatesOnlyAfterAllChanges() {
		budget("202609", "CONFIRMED", 1000);
		long first = spend("2026-09-18", 600, "PENDING", null);
		long second = spend("2026-09-18", 600, "PENDING", null);
		transactions.classifyPendingTransactions(userId, new BulkTransactionClassificationRequest(List.of(
				new BulkTransactionClassificationRequest.Item(first, 101, null, null),
				new BulkTransactionClassificationRequest.Item(second, 101, null, null))));
		assertThat(attachedCount()).isEqualTo(4);
		assertThat(countFor("budget_sticker_applications", userId)).isEqualTo(1);
	}

	@Test
	void concurrentRemovalsSucceedForEveryDistinctFurnitureAndRejectDuplicate() throws Exception {
		budget("202609", "CONFIRMED", 1000);
		spend("2026-09-18", 2000, "CONFIRMED", 101);
		rooms.getRoom(userId);
		long sofa = target("SOFA"), diningTable = target("DINING_TABLE"), tv = target("TV");
		var results = concurrently(List.of(() -> removeCode(sofa), () -> removeCode(sofa), () -> removeCode(diningTable), () -> removeCode(tv)));
		assertThat(results).containsExactlyInAnyOrder("SUCCESS", "ROOM_003", "SUCCESS", "SUCCESS");
		assertThat(attachedCount()).isEqualTo(1);
		assertThat(rooms.getRoom(userId).stickers().removableToday()).isTrue();
	}

	@Test
	void concurrentInitialAttachmentAndRemovalNeverReattachRemovedSticker() throws Exception {
		defaults.provision(userId);
		budget("202609", "CONFIRMED", 1000);
		spend("2026-09-18", 2000, "CONFIRMED", 101);
		long sofa = target("SOFA");
		concurrently(List.of(() -> { stickers.synchronize(userId); return "SYNC"; }, () -> removeCode(sofa)));
		assertThat(attachedCount()).isEqualTo(3);
		assertThat(countFor("budget_sticker_applications", userId)).isEqualTo(1);
	}

	@Test
	void rollbackRestoresAttachmentHistoryAndStickerState() {
		defaults.provision(userId);
		budget("202609", "CONFIRMED", 1000);
		spend("2026-09-18", 2000, "CONFIRMED", 101);
		long sofa = target("SOFA");
		var tx = new TransactionTemplate(transactionManager);
		assertThatThrownBy(() -> tx.executeWithoutResult(status -> {
			stickers.remove(userId, sofa);
			throw new IllegalStateException("rollback");
		})).isInstanceOf(IllegalStateException.class);
		assertThat(attachedCount()).isZero();
		assertThat(countFor("budget_sticker_applications", userId)).isZero();
		assertThat(countFor("room_sticker_states", userId)).isZero();
		assertThat(stickers.remove(userId, sofa).stickers().count()).isEqualTo(3);
	}

	@Test
	void roomReadsActualCoinAndAttendanceWithoutGrantingAgain() {
		jdbc.sql("INSERT INTO fin_coin (user_id, delta, balance_after, reason_code, grant_date) VALUES (:id, 10, 10, 'ATTEND', '2026-09-18'), (:id, -3, 7, 'PURCHASE', '2026-09-18')")
				.param("id", userId).update();
		var room = rooms.getRoom(userId);
		assertThat(room.coin().balance()).isEqualTo(7);
		assertThat(room.attendance().checkedToday()).isTrue();
		assertThat(countFor("fin_coin", userId)).isEqualTo(2);
		testClock.set(Instant.parse("2026-09-18T15:00:00Z"));
		assertThat(rooms.getRoom(userId).attendance().checkedToday()).isFalse();
	}

	@Test
	void documentsRemovalAndStickerFields() throws Exception {
		mvc.perform(get("/v3/api-docs")).andExpect(status().isOk())
				.andExpect(jsonPath("$.paths['/api/v1/room/stickers/removals'].post.responses['409']").exists())
				.andExpect(jsonPath("$.paths['/api/v1/room/stickers/removals'].post.responses['409'].description")
						.value(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("ROOM_002"))))
				.andExpect(jsonPath("$.components.schemas.RoomResponse.properties.stickers").exists())
				.andExpect(jsonPath("$.components.schemas.RoomResponse.properties.overEnvelopes.items.type").value("integer"))
				.andExpect(jsonPath("$.components.schemas.PlacedFurnitureResponse.properties.stickerAttached").exists())
				.andExpect(jsonPath("$.components.schemas.StickerStatusResponse.properties.count.maximum").doesNotExist())
				.andExpect(jsonPath("$.components.schemas.StickerStatusResponse.properties.total.enum").doesNotExist())
				.andExpect(jsonPath("$.paths['/api/v1/furnitures/{userFurnitureId}'].patch.responses['409']").exists());
	}

	private long createUser() {
		long id = users.save(User.create(UUID.randomUUID() + "@room.test", "encoded", "방테스터")).getId();
		testUsers.add(id);
		return id;
	}

	private long budget(String month, String status, long total) {
		jdbc.sql("INSERT INTO budgets (user_id, budget_month, status) VALUES (:user, :month, :status)")
				.param("user", userId).param("month", month).param("status", status).update();
		long id = jdbc.sql("SELECT id FROM budgets WHERE user_id = :user AND budget_month = :month")
				.param("user", userId).param("month", month).query(Long.class).single();
		jdbc.sql("INSERT INTO budget_envelopes (budget_id, envelope_id, proposed_amount, confirmed_amount) SELECT :id, id, IF(id = 1, :total, 0), IF(id = 1, :total, 0) FROM envelopes")
				.param("id", id).param("total", total).update();
		return id;
	}

	private BudgetConfirmRequest confirmation(long amount) {
		return new BudgetConfirmRequest(java.util.stream.IntStream.rangeClosed(1, 7)
				.mapToObj(id -> new BudgetConfirmRequest.EnvelopeAmount(id, id == 1 ? amount : 0L)).toList());
	}

	private long spend(String date, long amount, String confirmStatus, Integer category) {
		jdbc.sql("""
				INSERT INTO transactions (user_id, source, tx_type, amount, tx_date, tx_time, subcategory_id, confirm_status, exclude_tag, status)
				VALUES (:user, 'SEED', 'CARD', :amount, :date, '12:00:00', :category, :confirmed, 'NONE', 'NORMAL')
				""").param("user", userId).param("amount", amount).param("date", LocalDate.parse(date))
				.param("category", category).param("confirmed", confirmStatus).update();
		return jdbc.sql("SELECT MAX(id) FROM transactions WHERE user_id = :user").param("user", userId).query(Long.class).single();
	}

	private long target(String type) {
		return jdbc.sql("SELECT uf.id FROM user_furnitures uf JOIN items i ON i.id = uf.item_id WHERE uf.user_id = :user AND i.default_furniture_type = :type")
				.param("user", userId).param("type", type).query(Long.class).single();
	}

	private long countFor(String table, long id) {
		return jdbc.sql("SELECT COUNT(*) FROM " + table + " WHERE user_id = :id").param("id", id).query(Long.class).single();
	}

	private long attachedCount() {
		return jdbc.sql("SELECT COUNT(*) FROM user_furnitures WHERE user_id = :id AND sticker_attached = TRUE")
				.param("id", userId).query(Long.class).single();
	}

	private FurniturePlacementUpdateRequest moved() {
		return new FurniturePlacementUpdateRequest(true, FurniturePlacementStatus.FLOOR, FurniturePlacementDirection.FRONT_LEFT,
				new BigDecimal("100.123"), new BigDecimal("200.456"), 2);
	}

	private MockHttpServletRequestBuilder auth(MockHttpServletRequestBuilder request, long id) {
		return request.header("Authorization", "Bearer " + tokens.generateAccessToken(id));
	}

	private MockHttpServletRequestBuilder removal(long id) {
		return post("/api/v1/room/stickers/removals").contentType(APPLICATION_JSON).content("{\"userFurnitureId\":" + id + "}");
	}

	private void assertBusinessCode(Runnable operation, String code) {
		assertThatThrownBy(operation::run).isInstanceOfSatisfying(BusinessException.class,
				ex -> assertThat(ex.getErrorCode().getCode()).isEqualTo(code));
	}

	private String removeCode(long id) {
		try { stickers.remove(userId, id); return "SUCCESS"; }
		catch (BusinessException ex) { return ex.getErrorCode().getCode(); }
	}

	private List<String> concurrently(List<Callable<String>> jobs) throws Exception {
		var ready = new CountDownLatch(jobs.size());
		var start = new CountDownLatch(1);
		try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
			var futures = jobs.stream().map(job -> executor.submit(() -> {
				ready.countDown();
				if (!start.await(10, TimeUnit.SECONDS)) throw new IllegalStateException("start timeout");
				return job.call();
			})).toList();
			assertThat(ready.await(10, TimeUnit.SECONDS)).isTrue();
			start.countDown();
			var results = new ArrayList<String>();
			for (var future : futures) results.add(future.get(30, TimeUnit.SECONDS));
			return results;
		} finally { start.countDown(); }
	}


}
