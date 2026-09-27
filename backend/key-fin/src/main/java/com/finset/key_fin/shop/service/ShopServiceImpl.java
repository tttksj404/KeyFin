package com.finset.key_fin.shop.service;

import com.finset.key_fin.fincoin.entity.FinCoin;
import com.finset.key_fin.fincoin.repository.FinCoinRepository;
import com.finset.key_fin.furniture.entity.UserFurniture;
import com.finset.key_fin.furniture.repository.UserFurnitureRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.exception.CommonErrorCode;
import com.finset.key_fin.item.entity.Item;
import com.finset.key_fin.item.entity.ItemCategory;
import com.finset.key_fin.item.entity.ItemSlotType;
import com.finset.key_fin.item.entity.UserItem;
import com.finset.key_fin.item.repository.ItemRepository;
import com.finset.key_fin.item.repository.UserItemRepository;
import com.finset.key_fin.shop.dto.response.ShopItemResponse;
import com.finset.key_fin.shop.dto.response.ShopPurchaseResponse;
import com.finset.key_fin.shop.exception.ShopErrorCode;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

@Service
@RequiredArgsConstructor
public class ShopServiceImpl implements ShopService {
	private static final ZoneId PURCHASE_ZONE = ZoneId.of("Asia/Seoul");

	private final UserRepository userRepository;
	private final ItemRepository itemRepository;
	private final UserItemRepository userItemRepository;
	private final UserFurnitureRepository userFurnitureRepository;
	private final FinCoinRepository finCoinRepository;
	private final Clock clock;

	@Transactional(readOnly = true)
	@Override
	public List<ShopItemResponse> getItems(long userId, String itemCategory, String slotType) {
		ItemCategory category = parseFilter(ItemCategory.class, itemCategory);
		ItemSlotType slot = parseFilter(ItemSlotType.class, slotType);
		if (category != null && slot != null && (category == ItemCategory.AVATAR) != slot.isAvatarSlot()) {
			throw new BusinessException(CommonErrorCode.INVALID_INPUT_VALUE);
		}
		userRepository.findByIdAndDeletedAtIsNull(userId)
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_NOT_FOUND));
		List<Item> items = itemRepository.findShopItems(category, slot);
		if (items.isEmpty()) {
			return List.of();
		}
		Set<Long> ownedIds = new HashSet<>(userItemRepository.findOwnedItemIds(userId));
		ownedIds.addAll(userFurnitureRepository.findOwnedItemIds(userId));
		return items.stream().map(item -> ShopItemResponse.from(item, ownedIds.contains(item.getId()))).toList();
	}

	@Transactional
	@Override
	public ShopPurchaseResponse purchase(long userId, long itemId) {
		// 출석 보상과 동일한 잠금을 첫 DB 접근으로 획득한다. 잠금 전에 잔액 스냅샷을 만들지 않는다.
		User user = userRepository.findActiveByIdForUpdate(userId)
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_NOT_FOUND));
		Item item = itemRepository.findById(itemId).filter(Item::isActive)
				.orElseThrow(() -> new BusinessException(ShopErrorCode.ITEM_NOT_FOUND));
		int price = item.getPrice();
		if (price < 0) {
			throw new BusinessException(ShopErrorCode.INVALID_ITEM_PRICE);
		}
		boolean owned = switch (item.getItemCategory()) {
			case AVATAR -> userItemRepository.existsByUserIdAndItemId(userId, itemId);
			case FURNITURE -> userFurnitureRepository.existsByUserIdAndItemId(userId, itemId);
		};
		if (owned) {
			throw new BusinessException(ShopErrorCode.ITEM_ALREADY_OWNED);
		}
		int balance = finCoinRepository.findFirstByUserIdOrderByIdDesc(userId)
				.map(FinCoin::getBalanceAfter).orElse(0);
		if (balance < price) {
			throw new BusinessException(ShopErrorCode.INSUFFICIENT_COINS);
		}

		Long userItemId = null;
		Long userFurnitureId = null;
		switch (item.getItemCategory()) {
			case AVATAR -> userItemId = userItemRepository.save(UserItem.acquire(user, item)).getId();
			case FURNITURE -> userFurnitureId = userFurnitureRepository.save(UserFurniture.acquire(user, item)).getId();
		}
		FinCoin coin = FinCoin.forPurchase(user, LocalDate.now(clock.withZone(PURCHASE_ZONE)), itemId, price, balance);
		finCoinRepository.saveAndFlush(coin);
		return new ShopPurchaseResponse(itemId, item.getItemCategory(), userItemId, userFurnitureId,
				price, coin.getBalanceAfter());
	}

	private <E extends Enum<E>> E parseFilter(Class<E> enumType, String value) {
		if (value == null) {
			return null;
		}
		try {
			return Enum.valueOf(enumType, value);
		} catch (IllegalArgumentException ignored) {
			throw new BusinessException(CommonErrorCode.INVALID_INPUT_VALUE);
		}
	}
}
