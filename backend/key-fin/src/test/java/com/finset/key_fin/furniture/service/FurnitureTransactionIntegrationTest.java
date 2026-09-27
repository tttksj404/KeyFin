package com.finset.key_fin.furniture.service;

import com.finset.key_fin.furniture.dto.request.FurniturePlacementUpdateRequest;
import com.finset.key_fin.furniture.dto.response.UserFurnitureResponse;
import com.finset.key_fin.furniture.entity.FurniturePlacementDirection;
import com.finset.key_fin.furniture.entity.FurniturePlacementStatus;
import com.finset.key_fin.support.SpringIntegrationTestSupport;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlConfig;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import java.math.BigDecimal;
import java.sql.SQLException;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import static com.finset.key_fin.furniture.FurnitureFixtures.*;
import static org.assertj.core.api.Assertions.*;

@Sql(scripts = {"/sql/furniture-cleanup.sql", "/sql/furniture-fixture.sql"},
		config = @SqlConfig(encoding = "UTF-8", transactionMode = SqlConfig.TransactionMode.ISOLATED))
@Sql(scripts = "/sql/furniture-cleanup.sql", executionPhase = Sql.ExecutionPhase.AFTER_TEST_METHOD,
		config = @SqlConfig(transactionMode = SqlConfig.TransactionMode.ISOLATED))
class FurnitureTransactionIntegrationTest extends SpringIntegrationTestSupport {
	@Autowired private FurnitureService service;
	@Autowired private JdbcClient jdbc;
	@Autowired private PlatformTransactionManager transactions;
	@Autowired private DefaultFurnitureService defaults;

	@BeforeEach
	void provideRequiredFurniture() {
		defaults.provision(88001);
	}

	@Test
	void databaseRejectsPartialPlacementAndOutOfSceneCoordinates() {
		assertThatThrownBy(() -> jdbc.sql("UPDATE user_furnitures SET placement_status = 'FLOOR' WHERE id = 88203").update())
				.isInstanceOf(DataAccessException.class).hasMessageContaining("chk_uf_placement_state")
				.rootCause().isInstanceOfSatisfying(SQLException.class, e -> assertThat(e.getErrorCode()).isEqualTo(3819));
		assertThatThrownBy(() -> jdbc.sql("UPDATE user_furnitures SET position_x = 327.001 WHERE id = 88201").update())
				.isInstanceOf(DataAccessException.class).hasMessageContaining("chk_uf_position_x")
				.rootCause().isInstanceOfSatisfying(SQLException.class, e -> assertThat(e.getErrorCode()).isEqualTo(3819));
		for (String positionY : new String[]{"-0.001", "586.001"}) {
			assertThatThrownBy(() -> jdbc.sql("UPDATE user_furnitures SET position_y = :positionY WHERE id = 88201")
					.param("positionY", new BigDecimal(positionY)).update())
					.isInstanceOf(DataAccessException.class).hasMessageContaining("chk_uf_position_y")
					.rootCause().isInstanceOfSatisfying(SQLException.class, e -> assertThat(e.getErrorCode()).isEqualTo(3819));
		}
	}

	@Test
	void failureBeforeCommitRollsBackAllPlacementFields() {
		var before = current(88201);
		var tx = new TransactionTemplate(transactions);
		assertThatThrownBy(() -> tx.executeWithoutResult(status -> {
			service.updatePlacement(88001, 88201, removal());
			assertThat(current(88201).placed()).isFalse();
			throw new IllegalStateException("failure before commit");
		})).isInstanceOf(IllegalStateException.class);
		assertThat(current(88201)).isEqualTo(before);
	}

	@Test
	void concurrentPlacementsPersistOneCompleteRequest() throws Exception {
		var firstRequest = placement(FurniturePlacementStatus.FLOOR);
		var secondRequest = new FurniturePlacementUpdateRequest(true, FurniturePlacementStatus.FLOOR,
				FurniturePlacementDirection.FRONT_LEFT, new BigDecimal("20.000"), new BigDecimal("40.000"), 5);
		var ready = new CountDownLatch(2);
		var start = new CountDownLatch(1);
		try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
			var first = executor.submit(() -> changeTogether(88203, firstRequest, ready, start));
			var second = executor.submit(() -> changeTogether(88203, secondRequest, ready, start));
			assertThat(ready.await(5, TimeUnit.SECONDS)).isTrue();
			start.countDown();
			var firstResult = first.get(15, TimeUnit.SECONDS);
			var secondResult = second.get(15, TimeUnit.SECONDS);
			assertThat(firstResult.positionX()).isEqualByComparingTo(firstRequest.positionX());
			assertThat(secondResult.positionX()).isEqualByComparingTo(secondRequest.positionX());
			assertThat(current(88203)).isIn(firstResult, secondResult);
		}
	}

	@Test
	void concurrentMoveAndRemovalNeverLeaveMixedState() throws Exception {
		var ready = new CountDownLatch(2);
		var start = new CountDownLatch(1);
		try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
			var move = executor.submit(() -> changeTogether(88201, placement(FurniturePlacementStatus.FLOOR), ready, start));
			var remove = executor.submit(() -> changeTogether(88201, removal(), ready, start));
			assertThat(ready.await(5, TimeUnit.SECONDS)).isTrue();
			start.countDown();
			var moved = move.get(15, TimeUnit.SECONDS);
			var removed = remove.get(15, TimeUnit.SECONDS);
			assertThat(moved.placed()).isTrue();
			assertThat(removed.placed()).isFalse();
			assertThat(current(88201)).isIn(moved, removed);
		}
	}

	private UserFurnitureResponse changeTogether(long id, FurniturePlacementUpdateRequest request,
			CountDownLatch ready, CountDownLatch start) throws InterruptedException {
		ready.countDown();
		if (!start.await(5, TimeUnit.SECONDS)) throw new IllegalStateException("start timeout");
		return service.updatePlacement(88001, id, request);
	}

	private UserFurnitureResponse current(long id) {
		return service.getFurnitures(88001, null).stream().filter(f -> f.userFurnitureId() == id).findFirst().orElseThrow();
	}
}
