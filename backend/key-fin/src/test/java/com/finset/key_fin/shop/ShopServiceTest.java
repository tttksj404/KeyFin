package com.finset.key_fin.shop;

import com.finset.key_fin.fincoin.entity.FinCoin;
import com.finset.key_fin.fincoin.repository.FinCoinRepository;
import com.finset.key_fin.furniture.entity.UserFurniture;
import com.finset.key_fin.furniture.repository.UserFurnitureRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.item.entity.Item;
import com.finset.key_fin.item.entity.ItemCategory;
import com.finset.key_fin.item.entity.ItemSlotType;
import com.finset.key_fin.item.entity.UserItem;
import com.finset.key_fin.item.repository.ItemRepository;
import com.finset.key_fin.item.repository.UserItemRepository;
import com.finset.key_fin.shop.dto.response.ShopItemResponse;
import com.finset.key_fin.shop.service.ShopServiceImpl;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.repository.UserRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.BeanUtils;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.Clock;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

class ShopServiceTest {
	private final UserRepository users = mock(UserRepository.class);
	private final ItemRepository items = mock(ItemRepository.class);
	private final UserItemRepository userItems = mock(UserItemRepository.class);
	private final UserFurnitureRepository furniture = mock(UserFurnitureRepository.class);
	private final FinCoinRepository coins = mock(FinCoinRepository.class);
	private final ShopServiceImpl service = new ShopServiceImpl(users, items, userItems, furniture, coins, Clock.systemUTC());
	private final User user = User.create("shop@test.io", "encoded", "테스터");

	@Test
	void readsCatalogAndOwnedIdsInBatches() {
		when(users.findByIdAndDeletedAtIsNull(1L)).thenReturn(Optional.of(user));
		when(items.findShopItems(null, null)).thenReturn(List.of(item(10, ItemCategory.AVATAR, 1), item(20, ItemCategory.FURNITURE, 1)));
		when(userItems.findOwnedItemIds(1L)).thenReturn(List.of(10L));
		when(furniture.findOwnedItemIds(1L)).thenReturn(List.of(20L));

		assertThat(service.getItems(1, null, null)).extracting(ShopItemResponse::owned).containsExactly(true, true);
		verify(items).findShopItems(null, null);
		verify(userItems).findOwnedItemIds(1L);
		verify(furniture).findOwnedItemIds(1L);
		verifyNoMoreInteractions(items, userItems, furniture);
		verifyNoInteractions(coins);
	}

	@Test
	void locksUserBeforeAnyCatalogOwnershipOrBalanceRead() {
		Item item = item(10, ItemCategory.AVATAR, 0);
		when(users.findActiveByIdForUpdate(1L)).thenReturn(Optional.of(user));
		when(items.findById(10L)).thenReturn(Optional.of(item));
		when(userItems.save(any())).thenAnswer(invocation -> invocation.getArgument(0));

		assertThat(service.purchase(1, 10).balance()).isZero();
		var order = inOrder(users, items, userItems, coins);
		order.verify(users).findActiveByIdForUpdate(1L);
		order.verify(items).findById(10L);
		order.verify(userItems).existsByUserIdAndItemId(1L, 10L);
		order.verify(coins).findFirstByUserIdOrderByIdDesc(1L);
		order.verify(userItems).save(any());
		order.verify(coins).saveAndFlush(any());
		verify(users, never()).findByIdAndDeletedAtIsNull(any());
	}

	@Test
	void unknownUserStopsBeforeReadingOtherTables() {
		assertThatThrownBy(() -> service.purchase(1, 10)).isInstanceOf(BusinessException.class);
		verify(users).findActiveByIdForUpdate(1L);
		verifyNoInteractions(items, userItems, furniture, coins);
	}

	@Test
	void purchaseLedgerAllowsFreeAndExactBalanceButRejectsInvalidAmounts() {
		LocalDate date = LocalDate.of(2026, 9, 17);
		FinCoin free = FinCoin.forPurchase(user, date, 10, 0, 0);
		assertThat(free.getDelta()).isZero();
		assertThat(free.getBalanceAfter()).isZero();
		FinCoin maximum = FinCoin.forPurchase(user, date, Long.MAX_VALUE, Integer.MAX_VALUE, Integer.MAX_VALUE);
		assertThat(maximum.getDelta()).isEqualTo(-Integer.MAX_VALUE);
		assertThat(maximum.getBalanceAfter()).isZero();
		assertThat(maximum.getRefId()).isEqualTo(Long.toString(Long.MAX_VALUE));
		assertThatThrownBy(() -> FinCoin.forPurchase(user, date, 10, -1, 100)).isInstanceOf(IllegalArgumentException.class);
		assertThatThrownBy(() -> FinCoin.forPurchase(user, date, 10, 101, 100)).isInstanceOf(IllegalArgumentException.class);
		assertThatThrownBy(() -> FinCoin.forPurchase(user, date, 10, 0, -1)).isInstanceOf(IllegalArgumentException.class);
		assertThatThrownBy(() -> FinCoin.forPurchase(user, date, 0, 0, 0)).isInstanceOf(IllegalArgumentException.class);
	}

	@Test
	void acquisitionFactoriesEnforceCategoryAndStartUnequipped() {
		Item avatar = item(10, ItemCategory.AVATAR, 1);
		Item furnishing = item(20, ItemCategory.FURNITURE, 1);
		assertThat(UserItem.acquire(user, avatar).isEquipped()).isFalse();
		UserFurniture acquired = UserFurniture.acquire(user, furnishing);
		assertThat(acquired.isPlaced()).isFalse();
		assertThat(acquired.getLayer()).isZero();
		assertThatThrownBy(() -> UserItem.acquire(user, furnishing)).isInstanceOf(IllegalArgumentException.class);
		assertThatThrownBy(() -> UserFurniture.acquire(user, avatar)).isInstanceOf(IllegalArgumentException.class);
	}

	private Item item(long id, ItemCategory category, int price) {
		Item item = BeanUtils.instantiateClass(Item.class);
		ReflectionTestUtils.setField(item, "id", id);
		ReflectionTestUtils.setField(item, "itemCategory", category);
		ReflectionTestUtils.setField(item, "slotType", category == ItemCategory.AVATAR ? ItemSlotType.HEAD : ItemSlotType.FLOOR);
		ReflectionTestUtils.setField(item, "price", price);
		return item;
	}
}
