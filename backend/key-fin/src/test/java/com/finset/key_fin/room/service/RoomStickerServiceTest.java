package com.finset.key_fin.room.service;

import com.finset.key_fin.budget.entity.Budget;
import com.finset.key_fin.budget.repository.BudgetRepository;
import com.finset.key_fin.budget.service.BudgetOverrunService;
import com.finset.key_fin.budget.service.EnvelopeBalanceService;
import com.finset.key_fin.budget.service.EnvelopeBalanceService.EnvelopeBalance;
import com.finset.key_fin.furniture.entity.FurniturePlacementDirection;
import com.finset.key_fin.furniture.entity.FurniturePlacementStatus;
import com.finset.key_fin.furniture.entity.UserFurniture;
import com.finset.key_fin.furniture.repository.UserFurnitureRepository;
import com.finset.key_fin.furniture.service.DefaultFurnitureService;
import com.finset.key_fin.item.entity.ItemSlotType;
import com.finset.key_fin.room.repository.RoomStickerRepository;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.repository.UserRepository;
import com.finset.key_fin.user.repository.UserSettingsRepository;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.test.util.ReflectionTestUtils;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicBoolean;

import static com.finset.key_fin.furniture.FurnitureFixtures.owned;
import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

class RoomStickerServiceTest {

	private final UserRepository users = mock(UserRepository.class);
	private final UserFurnitureRepository furnitures = mock(UserFurnitureRepository.class);
	private final DefaultFurnitureService defaults = mock(DefaultFurnitureService.class);
	private final BudgetRepository budgets = mock(BudgetRepository.class);
	private final EnvelopeBalanceService balances = mock(EnvelopeBalanceService.class);
	private final RoomStickerRepository applications = mock(RoomStickerRepository.class);
	private final EntityManager entityManager = mock(EntityManager.class);
	private final RoomStickerService service = new RoomStickerService(users, furnitures, defaults,
			new BudgetOverrunService(budgets, mock(UserSettingsRepository.class), balances), applications,
			entityManager, Clock.fixed(Instant.parse("2026-09-18T03:00:00Z"), ZoneOffset.UTC));
	private final UserFurniture floor = placed(1L, ItemSlotType.FLOOR, FurniturePlacementStatus.FLOOR);
	private final UserFurniture stored = placed(2L, ItemSlotType.FLOOR, FurniturePlacementStatus.FLOOR);
	private final UserFurniture wall = placed(3L, ItemSlotType.WALL, FurniturePlacementStatus.LEFT_WALL);
	private final List<UserFurniture> owned = List.of(floor, stored, wall);

	@BeforeEach
	void setUp() {
		var applied = new AtomicBoolean();
		when(applications.wasApplied(10L)).thenAnswer(invocation -> applied.get());
		doAnswer(invocation -> { applied.set(true); return null; })
				.when(applications).recordApplication(eq(1L), eq(10L), any());
		doAnswer(invocation -> { applied.set(false); return null; })
				.when(applications).clearApplication(10L);
		when(users.findActiveByIdForUpdate(1L)).thenReturn(Optional.of(mock(User.class)));
		when(furnitures.findByUserIdOrderByIdAsc(1L)).thenReturn(owned);
		var budget = Budget.propose(null, "202609");
		budget.confirm();
		ReflectionTestUtils.setField(budget, "id", 10L);
		when(budgets.findByUserIdAndBudgetMonth(1L, "202609")).thenReturn(Optional.of(budget));
		spending(1500);
		assertThat(service.synchronize(1L).count()).isEqualTo(2);
		stored.unplace();
	}

	@ParameterizedTest
	@ValueSource(longs = {0, 1000})
	void recoveredTotalBudgetClearsPlacedAndStoredStickers(long remainingSpending) {
		spending(remainingSpending);

		var status = service.synchronize(1L);

		assertThat(status.count()).isZero();
		assertThat(status.total()).isEqualTo(1);
		assertThat(status.removableToday()).isFalse();
		assertThat(owned).allSatisfy(f -> assertThat(f.isStickerAttached()).isFalse());
		assertThat(service.synchronize(1L)).isEqualTo(status);
		verify(applications, times(1)).recordApplication(eq(1L), eq(10L), any());
		verify(applications, times(2)).clearApplication(10L);
	}

	@Test
	void partialRecoveryKeepsStickersWhileTotalBudgetIsStillExceeded() {
		spending(1001);

		assertThat(service.synchronize(1L).count()).isEqualTo(1);
		assertThat(floor.isStickerAttached()).isTrue();
		assertThat(stored.isStickerAttached()).isTrue();
		assertThat(wall.isStickerAttached()).isFalse();
		verify(applications, never()).clearApplication(anyLong());
	}

	@Test
	void totalRecoveryClearsStickersEvenWhenOneEnvelopeIsStillExceeded() {
		when(balances.getMonthlyBalances(1L, "202609")).thenReturn(List.of(
				new EnvelopeBalance(1, "외식", 1000L, 1001), new EnvelopeBalance(4, "취미·여가", 1000L, 0)));

		assertThat(service.synchronize(1L).count()).isZero();
		assertThat(stored.isStickerAttached()).isFalse();
	}

	@Test
	void recoveryAllowsRepeatedReattachmentInTheSameBudgetPeriod() {
		for (int cycle = 0; cycle < 2; cycle++) {
			spending(1000);
			assertThat(service.synchronize(1L).count()).isZero();
			spending(1500);

			assertThat(service.synchronize(1L).count()).isEqualTo(1);
			assertThat(floor.isStickerAttached()).isTrue();
			assertThat(stored.isStickerAttached()).isFalse();
			assertThat(wall.isStickerAttached()).isFalse();
		}
		verify(applications, times(3)).recordApplication(eq(1L), eq(10L), any());
		verify(applications, times(2)).clearApplication(10L);
	}

	@Test
	void manualRemovalDoesNotReattachWhileBudgetRemainsExceeded() {
		when(furnitures.findByIdAndUserId(1L, 1L)).thenReturn(Optional.of(floor));
		service.remove(1L, 1L);
		spending(2000);

		assertThat(service.synchronize(1L).count()).isZero();
		assertThat(floor.isStickerAttached()).isFalse();
		assertThat(stored.isStickerAttached()).isTrue();
		verify(applications, times(1)).recordApplication(eq(1L), eq(10L), any());
		verify(applications, never()).clearApplication(anyLong());
	}

	@Test
	void missingOrUnconfirmedBudgetDoesNotCountAsRecovery() {
		when(budgets.findByUserIdAndBudgetMonth(1L, "202609")).thenReturn(Optional.empty());
		assertThat(service.synchronize(1L).count()).isEqualTo(1);
		when(budgets.findByUserIdAndBudgetMonth(1L, "202609"))
				.thenReturn(Optional.of(Budget.propose(null, "202609")));
		assertThat(service.synchronize(1L).count()).isEqualTo(1);
		assertThat(stored.isStickerAttached()).isTrue();
		verify(applications, never()).clearApplication(anyLong());
	}

	private void spending(long amount) {
		when(balances.getMonthlyBalances(1L, "202609"))
				.thenReturn(List.of(new EnvelopeBalance(1, "외식", 1000L, amount)));
	}

	private static UserFurniture placed(long id, ItemSlotType slot, FurniturePlacementStatus status) {
		var furniture = owned(id, slot);
		furniture.place(status, FurniturePlacementDirection.FRONT_RIGHT, BigDecimal.ZERO, BigDecimal.ZERO, 0);
		return furniture;
	}
}
