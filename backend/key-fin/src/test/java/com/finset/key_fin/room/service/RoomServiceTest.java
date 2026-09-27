package com.finset.key_fin.room.service;

import com.finset.key_fin.budget.service.BudgetOverrunService;

import com.finset.key_fin.furniture.dto.response.PlacedFurnitureResponse;
import com.finset.key_fin.furniture.entity.FurniturePlacementDirection;
import com.finset.key_fin.furniture.entity.FurniturePlacementStatus;
import com.finset.key_fin.furniture.service.FurnitureService;
import com.finset.key_fin.item.dto.response.AvatarEquipmentResponse;
import com.finset.key_fin.item.entity.ItemSlotType;
import com.finset.key_fin.item.service.ItemService;
import com.finset.key_fin.fincoin.repository.FinCoinRepository;
import com.finset.key_fin.fincoin.entity.FinCoin;
import com.finset.key_fin.fincoin.entity.FinCoinReason;
import com.finset.key_fin.room.dto.response.StickerStatusResponse;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;
import java.util.Optional;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

class RoomServiceTest {
	private final ItemService items = mock(ItemService.class);
	private final FurnitureService furnitures = mock(FurnitureService.class);
	private final RoomStickerService stickers = mock(RoomStickerService.class);
	private final FinCoinRepository coins = mock(FinCoinRepository.class);
	private final BudgetOverrunService overruns = mock(BudgetOverrunService.class);
	private final RoomService service = new RoomServiceImpl(items, furnitures, stickers, overruns, coins,
			Clock.fixed(Instant.parse("2026-09-18T15:00:00Z"), ZoneOffset.UTC));

	@Test
	void usesAuthenticatedUsersActualPlacementsIncludingEmptyRoom() {
		when(items.getEquipment(1L)).thenReturn(new AvatarEquipmentResponse(List.of()));
		var placed = new PlacedFurnitureResponse(201L, 4L, ItemSlotType.FLOOR, "sofa_blue",
				FurniturePlacementStatus.FLOOR, FurniturePlacementDirection.FRONT_LEFT,
				new BigDecimal("165.123"), new BigDecimal("280.456"), -2, null, null, false, true);
		when(furnitures.getPlacedFurnitures(1L)).thenReturn(List.of(placed)).thenReturn(List.of());
		assertThat(service.getRoom(1).furnitures()).containsExactly(placed);
		assertThat(service.getRoom(1).furnitures()).isEmpty();
		verify(furnitures, times(2)).getPlacedFurnitures(1L);
	}

	@Test
	void readsLedgerAndKoreanAttendanceWithoutGrantingRewards() {
		when(items.getEquipment(1L)).thenReturn(new AvatarEquipmentResponse(List.of()));
		var coin = mock(FinCoin.class);
		when(coin.getBalanceAfter()).thenReturn(37);
		when(coins.findFirstByUserIdOrderByIdDesc(1L)).thenReturn(Optional.of(coin));
		when(coins.existsByUserIdAndGrantDateAndReasonCode(1L, LocalDate.of(2026, 9, 19), FinCoinReason.ATTEND)).thenReturn(true);
		when(stickers.synchronize(1L)).thenReturn(new StickerStatusResponse(2, 4, false));
		when(overruns.currentExceededEnvelopeIds(1L, LocalDate.of(2026, 9, 19))).thenReturn(List.of(1, 4));
		var result = service.getRoom(1L);
		assertThat(result.coin().balance()).isEqualTo(37);
		assertThat(result.attendance().checkedToday()).isTrue();
		assertThat(result.stickers().count()).isEqualTo(2);
		assertThat(result.overEnvelopes()).containsExactly(1, 4);
		verify(coins, never()).save(any());
		when(coins.findFirstByUserIdOrderByIdDesc(1L)).thenReturn(Optional.empty());
		assertThat(service.getRoom(1L).coin().balance()).isZero();
	}
}
