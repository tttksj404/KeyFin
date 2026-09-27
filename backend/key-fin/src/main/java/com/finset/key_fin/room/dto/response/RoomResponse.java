package com.finset.key_fin.room.dto.response;

import com.finset.key_fin.furniture.dto.response.PlacedFurnitureResponse;
import com.finset.key_fin.item.dto.response.EquippedItemResponse;

import java.time.LocalDateTime;
import java.util.List;

public record RoomResponse(
		AvatarResponse avatar,
		List<PlacedFurnitureResponse> furnitures,
		CoinResponse coin,
		AttendanceResponse attendance,
		StickerStatusResponse stickers,
		List<Integer> overEnvelopes
) {

	public record AvatarResponse(
			List<EquippedItemResponse> equipped,
			ReactionResponse reaction
	) {
	}

	public record ReactionResponse(
			String type,
			LocalDateTime until
	) {
	}

	public record CoinResponse(int balance) {
	}

	public record AttendanceResponse(boolean checkedToday) {
	}
}
