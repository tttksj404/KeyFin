package com.finset.key_fin.furniture.service;

import com.finset.key_fin.furniture.dto.request.FurniturePlacementUpdateRequest;
import com.finset.key_fin.furniture.dto.request.FurniturePlacementsUpdateRequest;
import com.finset.key_fin.furniture.dto.response.PlacedFurnitureResponse;
import com.finset.key_fin.furniture.dto.response.UserFurnitureResponse;
import com.finset.key_fin.furniture.entity.FurnitureType;
import com.finset.key_fin.furniture.entity.UserFurniture;
import com.finset.key_fin.furniture.exception.FurnitureErrorCode;
import com.finset.key_fin.furniture.repository.UserFurnitureRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.exception.CommonErrorCode;
import com.finset.key_fin.item.entity.ItemSlotType;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.EnumMap;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;

@Service
@RequiredArgsConstructor
public class FurnitureServiceImpl implements FurnitureService {
	private final UserFurnitureRepository userFurnitureRepository;
	private final UserRepository userRepository;

	@Transactional(readOnly = true)
	@Override
	public List<UserFurnitureResponse> getFurnitures(long userId, String slotType) {
		ItemSlotType filter = parseFurnitureSlot(slotType);
		validateActiveUser(userId);
		var furnitures = filter == null
				? userFurnitureRepository.findByUserIdOrderByIdAsc(userId)
				: userFurnitureRepository.findByUserIdAndItemSlotTypeOrderByIdAsc(userId, filter);
		return furnitures.stream().map(UserFurnitureResponse::from).toList();
	}

	@Transactional(readOnly = true)
	@Override
	public List<PlacedFurnitureResponse> getPlacedFurnitures(long userId) {
		validateActiveUser(userId);
		return userFurnitureRepository.findByUserIdAndPlacementStatusIsNotNullOrderByIdAsc(userId)
				.stream().map(PlacedFurnitureResponse::from).toList();
	}

	@Transactional
	@Override
	public UserFurnitureResponse updatePlacement(long userId, long userFurnitureId, FurniturePlacementUpdateRequest request) {
		userRepository.findActiveByIdForUpdate(userId)
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_NOT_FOUND));
		var target = userFurnitureRepository.findByIdAndUserId(userFurnitureId, userId)
				.orElseThrow(() -> new BusinessException(FurnitureErrorCode.USER_FURNITURE_NOT_FOUND));
		if (!request.placed() && !target.canUnplace()) {
			throw new BusinessException(FurnitureErrorCode.DEFAULT_FURNITURE_CANNOT_UNPLACE);
		}
		if (request.placed()) target.validatePlacementStatus(request.placementStatus());
		var finalLayout = new ArrayList<>(userFurnitureRepository.findByUserIdAndPlacementStatusIsNotNullOrderByIdAsc(userId));
		finalLayout.removeIf(f -> f.getId().equals(userFurnitureId));
		if (request.placed()) finalLayout.add(target);
		validateEssentialCounts(finalLayout);
		if (request.placed()) {
			target.place(request.placementStatus(), request.placementDirection(), request.positionX(), request.positionY(),
					request.layer() == null ? 0 : request.layer());
		} else {
			target.unplace();
		}
		userFurnitureRepository.flush();
		return UserFurnitureResponse.from(target);
	}

	@Transactional
	@Override
	public List<UserFurnitureResponse> updatePlacements(long userId, FurniturePlacementsUpdateRequest request) {
		userRepository.findActiveByIdForUpdate(userId)
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_NOT_FOUND));
		var owned = userFurnitureRepository.findByUserIdOrderByIdAsc(userId);
		var byId = new HashMap<Long, UserFurniture>();
		owned.forEach(f -> byId.put(f.getId(), f));
		var ids = new HashSet<Long>();
		for (var placement : request.placements()) {
			if (!ids.add(placement.userFurnitureId())) {
				throw new BusinessException(CommonErrorCode.INVALID_INPUT_VALUE);
			}
		}
		var finalLayout = new ArrayList<UserFurniture>();
		for (var placement : request.placements()) {
			var furniture = byId.get(placement.userFurnitureId());
			if (furniture == null) throw new BusinessException(FurnitureErrorCode.USER_FURNITURE_NOT_FOUND);
			furniture.validatePlacementStatus(placement.placementStatus());
			finalLayout.add(furniture);
		}
		validateEssentialCounts(finalLayout);

		// Capture before clearing old placements. Replacement never counts as a sticker removal.
		var stickerTypes = EnumSet.noneOf(FurnitureType.class);
		for (var furniture : owned) {
			var type = furniture.getItem().getFurnitureType();
			if (type != null && furniture.isPlaced() && furniture.isStickerAttached()) stickerTypes.add(type);
		}
		for (var furniture : owned) {
			if (!ids.contains(furniture.getId())) furniture.unplace();
			// Essential stickers belong to the type; ordinary stickers stay with the owned item.
			if (furniture.getItem().getFurnitureType() != null) furniture.removeSticker();
		}
		for (var placement : request.placements()) {
			var furniture = byId.get(placement.userFurnitureId());
			furniture.place(placement.placementStatus(), placement.placementDirection(),
					placement.positionX(), placement.positionY(), placement.layer() == null ? 0 : placement.layer());
			if (stickerTypes.contains(furniture.getItem().getFurnitureType())) furniture.attachSticker();
		}
		userFurnitureRepository.flush();
		return owned.stream().map(UserFurnitureResponse::from).toList();
	}

	private static void validateEssentialCounts(List<UserFurniture> finalLayout) {
		var counts = new EnumMap<FurnitureType, Integer>(FurnitureType.class);
		for (var furniture : finalLayout) {
			var type = furniture.getItem().getFurnitureType();
			if (type != null) counts.merge(type, 1, Integer::sum);
		}
		for (var type : FurnitureType.values()) {
			if (counts.getOrDefault(type, 0) != 1) {
				throw new BusinessException(FurnitureErrorCode.ESSENTIAL_FURNITURE_COUNT_INVALID);
			}
		}
	}

	private void validateActiveUser(long userId) {
		userRepository.findByIdAndDeletedAtIsNull(userId)
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_NOT_FOUND));
	}

	private ItemSlotType parseFurnitureSlot(String value) {
		if (value == null) return null;
		try {
			ItemSlotType slot = ItemSlotType.valueOf(value);
			if (slot == ItemSlotType.FLOOR || slot == ItemSlotType.WALL) return slot;
		} catch (IllegalArgumentException ignored) {
			// 빈 값과 알 수 없는 유형도 동일한 입력 오류로 응답한다.
		}
		throw new BusinessException(CommonErrorCode.INVALID_INPUT_VALUE);
	}
}
