package com.finset.key_fin.room.service;

import com.finset.key_fin.budget.service.BudgetOverrunService;
import com.finset.key_fin.furniture.entity.FurniturePlacementStatus;
import com.finset.key_fin.furniture.entity.UserFurniture;
import com.finset.key_fin.furniture.exception.FurnitureErrorCode;
import com.finset.key_fin.furniture.repository.UserFurnitureRepository;
import com.finset.key_fin.furniture.service.DefaultFurnitureService;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.room.dto.response.StickerRemovalResponse;
import com.finset.key_fin.room.dto.response.StickerStatusResponse;
import com.finset.key_fin.room.exception.RoomErrorCode;
import com.finset.key_fin.room.repository.RoomStickerRepository;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import jakarta.persistence.EntityManager;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.List;

@Service
@RequiredArgsConstructor
public class RoomStickerService {
	private static final ZoneId KST = ZoneId.of("Asia/Seoul");
	private final UserRepository users;
	private final UserFurnitureRepository furnitures;
	private final DefaultFurnitureService defaults;
	private final BudgetOverrunService budgets;
	private final RoomStickerRepository stickers;
	private final EntityManager entityManager;
	private final Clock clock;

	@Transactional
	public StickerStatusResponse synchronize(long userId) {
		lockUser(userId);
		LocalDateTime now = LocalDateTime.now(clock.withZone(KST));
		var targets = synchronizeLocked(userId, now);
		return status(targets);
	}

	@Transactional
	public StickerRemovalResponse remove(long userId, long userFurnitureId) {
		lockUser(userId);
		var target = furnitures.findByIdAndUserId(userFurnitureId, userId)
				.orElseThrow(() -> new BusinessException(FurnitureErrorCode.USER_FURNITURE_NOT_FOUND));
		if (target.getPlacementStatus() != FurniturePlacementStatus.FLOOR) {
			throw new BusinessException(RoomErrorCode.NOT_STICKER_TARGET);
		}
		LocalDateTime now = LocalDateTime.now(clock.withZone(KST));
		var targets = synchronizeLocked(userId, now);
		if (!target.isStickerAttached()) {
			throw new BusinessException(RoomErrorCode.STICKER_NOT_ATTACHED);
		}
		target.removeSticker();
		return new StickerRemovalResponse(userFurnitureId, false, status(targets));
	}

	private List<UserFurniture> synchronizeLocked(long userId, LocalDateTime now) {
		defaults.provision(userId);
		// JDBC aggregation must see pending JPA classifications and budget confirmation.
		entityManager.flush();
		var owned = furnitures.findByUserIdOrderByIdAsc(userId);
		var targets = owned.stream()
				.filter(f -> f.getPlacementStatus() == FurniturePlacementStatus.FLOOR).toList();
		budgets.currentBudgetOverrun(userId, now.toLocalDate()).ifPresent(budget -> {
			if (!budget.exceeded()) {
				// Recovery also clears stored furniture so reinstalling cannot restore an old sticker.
				owned.forEach(UserFurniture::removeSticker);
				// A later overrun starts a new application, even within the same budget period.
				stickers.clearApplication(budget.budgetId());
			} else if (!stickers.wasApplied(budget.budgetId())) {
				stickers.recordApplication(userId, budget.budgetId(), now);
				targets.forEach(UserFurniture::attachSticker);
			}
		});
		return targets;
	}

	private StickerStatusResponse status(List<UserFurniture> targets) {
		int count = (int) targets.stream().filter(UserFurniture::isStickerAttached).count();
		return new StickerStatusResponse(count, targets.size(), count > 0);
	}

	private void lockUser(long userId) {
		users.findActiveByIdForUpdate(userId)
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_NOT_FOUND));
	}
}
