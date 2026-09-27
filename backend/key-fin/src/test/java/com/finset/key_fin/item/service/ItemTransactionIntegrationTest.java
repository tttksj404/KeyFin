package com.finset.key_fin.item.service;

import com.finset.key_fin.item.dto.response.AvatarEquipmentResponse;
import com.finset.key_fin.item.dto.response.EquippedItemResponse;
import com.finset.key_fin.support.SpringIntegrationTestSupport;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlConfig;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import static com.finset.key_fin.item.entity.ItemSlotType.UPPER_BODY;
import static org.assertj.core.api.Assertions.*;

@Sql(scripts = {"/sql/item-cleanup.sql", "/sql/item-fixture.sql"},
		config = @SqlConfig(encoding = "UTF-8", transactionMode = SqlConfig.TransactionMode.ISOLATED))
@Sql(scripts = "/sql/item-cleanup.sql", executionPhase = Sql.ExecutionPhase.AFTER_TEST_METHOD,
		config = @SqlConfig(transactionMode = SqlConfig.TransactionMode.ISOLATED))
class ItemTransactionIntegrationTest extends SpringIntegrationTestSupport {
	@Autowired private ItemService service;
	@Autowired private JdbcClient jdbc;
	@Autowired private PlatformTransactionManager transactions;

	@Test
	void databaseRejectsDuplicateSlotAndWrongCatalogSlot() {
		assertThatThrownBy(() -> jdbc.sql("UPDATE user_items SET equipped_slot = 'UPPER_BODY' WHERE id = 7202").update())
				.isInstanceOf(DataIntegrityViolationException.class);
		assertThatThrownBy(() -> jdbc.sql("UPDATE user_items SET equipped_slot = 'FOOTWEAR' WHERE id = 7204").update())
				.isInstanceOf(DataIntegrityViolationException.class);
	}

	@Test
	void failureBeforeCommitRollsBackBothSidesOfReplacement() {
		var tx = new TransactionTemplate(transactions);
		assertThatThrownBy(() -> tx.executeWithoutResult(status -> {
			service.updateEquipment(971L, 7202L, true);
			assertThat(currentTop()).isEqualTo(7202L);
			throw new IllegalStateException("failure before commit");
		})).isInstanceOf(IllegalStateException.class);
		assertThat(currentTop()).isEqualTo(7201L);
		assertThat(jdbc.sql("SELECT COUNT(*) FROM user_items WHERE id = 7202 AND equipped_slot IS NULL")
				.query(Long.class).single()).isEqualTo(1);
	}

	@Test
	void concurrentReplacementsSerializeEvenWhenSlotInitiallyEmpty() throws Exception {
		jdbc.sql("UPDATE user_items SET equipped_slot = NULL WHERE user_id = 971 AND equipped_slot = 'UPPER_BODY'").update();
		for (int round = 0; round < 4; round++) {
			var ready = new CountDownLatch(2);
			var start = new CountDownLatch(1);
			try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
				Future<AvatarEquipmentResponse> first = executor.submit(() -> equipTogether(7201L, ready, start));
				Future<AvatarEquipmentResponse> second = executor.submit(() -> equipTogether(7202L, ready, start));
				assertThat(ready.await(5, TimeUnit.SECONDS)).isTrue();
				start.countDown();
				assertThat(first.get(15, TimeUnit.SECONDS).equipped()).filteredOn(r -> r.slotType() == UPPER_BODY)
						.extracting(EquippedItemResponse::userItemId).containsExactly(7201L);
				assertThat(second.get(15, TimeUnit.SECONDS).equipped()).filteredOn(r -> r.slotType() == UPPER_BODY)
						.extracting(EquippedItemResponse::userItemId).containsExactly(7202L);
			}
			assertThat(currentTop()).isIn(7201L, 7202L);
			assertThat(service.getEquipment(971L).equipped()).hasSize(2);
		}
	}

	@Test
	void concurrentEquipAndStaleUnequipPreserveReplacement() throws Exception {
		var ready = new CountDownLatch(2);
		var start = new CountDownLatch(1);
		try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
			var equip = executor.submit(() -> equipTogether(7202L, ready, start));
			var remove = executor.submit(() -> {
				ready.countDown();
				if (!start.await(5, TimeUnit.SECONDS)) throw new IllegalStateException("start timeout");
				return service.updateEquipment(971L, 7201L, false);
			});
			assertThat(ready.await(5, TimeUnit.SECONDS)).isTrue();
			start.countDown();
			equip.get(15, TimeUnit.SECONDS);
			remove.get(15, TimeUnit.SECONDS);
		}
		assertThat(currentTop()).isEqualTo(7202L);
	}

	private AvatarEquipmentResponse equipTogether(long id, CountDownLatch ready, CountDownLatch start)
			throws InterruptedException {
		ready.countDown();
		if (!start.await(5, TimeUnit.SECONDS)) throw new IllegalStateException("start timeout");
		return service.updateEquipment(971L, id, true);
	}

	private long currentTop() {
		return jdbc.sql("SELECT id FROM user_items WHERE user_id = 971 AND equipped_slot = 'UPPER_BODY'")
				.query(Long.class).single();
	}
}
