package com.finset.key_fin.room.service;

import com.finset.key_fin.budget.service.BudgetOverrunService;

import com.finset.key_fin.furniture.service.FurnitureService;
import com.finset.key_fin.fincoin.entity.FinCoin;
import com.finset.key_fin.fincoin.entity.FinCoinReason;
import com.finset.key_fin.fincoin.repository.FinCoinRepository;
import com.finset.key_fin.item.service.ItemService;
import com.finset.key_fin.room.dto.response.RoomResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.LocalDate;
import java.time.ZoneId;

@Service
@RequiredArgsConstructor
public class RoomServiceImpl implements RoomService {

	private final ItemService itemService;
	private final FurnitureService furnitureService;
	private final RoomStickerService stickerService;
	private final BudgetOverrunService budgetOverrunService;
	private final FinCoinRepository finCoins;
	private final Clock clock;

	@Transactional
	@Override
	public RoomResponse getRoom(long userId) {
		// Lock before snapshot reads; never create a budget or grant attendance here.
		var stickers = stickerService.synchronize(userId);
		var equipped = itemService.getEquipment(userId).equipped();
		var furnitures = furnitureService.getPlacedFurnitures(userId);
		var today = LocalDate.now(clock.withZone(ZoneId.of("Asia/Seoul")));

		return new RoomResponse(
				new RoomResponse.AvatarResponse(equipped, null),
				furnitures,
				new RoomResponse.CoinResponse(finCoins.findFirstByUserIdOrderByIdDesc(userId)
						.map(FinCoin::getBalanceAfter).orElse(0)),
				new RoomResponse.AttendanceResponse(finCoins.existsByUserIdAndGrantDateAndReasonCode(
						userId, today, FinCoinReason.ATTEND)),
				stickers,
				budgetOverrunService.currentExceededEnvelopeIds(userId, today)
		);
	}
}
