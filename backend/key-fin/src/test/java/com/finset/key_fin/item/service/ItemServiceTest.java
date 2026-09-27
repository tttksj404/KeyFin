package com.finset.key_fin.item.service;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.exception.CommonErrorCode;
import com.finset.key_fin.item.dto.response.EquippedItemResponse;
import com.finset.key_fin.item.entity.UserItem;
import com.finset.key_fin.item.exception.ItemErrorCode;
import com.finset.key_fin.item.repository.UserItemRepository;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;
import java.util.Optional;

import static com.finset.key_fin.item.ItemFixtures.owned;
import static com.finset.key_fin.item.entity.ItemSlotType.*;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

class ItemServiceTest {
	private final UserItemRepository items = mock(UserItemRepository.class);
	private final UserRepository users = mock(UserRepository.class);
	private final ItemService service = new ItemServiceImpl(items, users);

	@BeforeEach
	void setUp() {
		User user = User.create("item@test.io", "hash", "아이템");
		lenient().when(users.findActiveByIdForUpdate(1L)).thenReturn(Optional.of(user));
		lenient().when(users.findByIdAndDeletedAtIsNull(1L)).thenReturn(Optional.of(user));
	}

	@Test
	void listsOwnedItemsIncludingInactiveCatalogEntries() {
		UserItem inactive = owned(2L, UPPER_BODY, false);
		ReflectionTestUtils.setField(inactive.getItem(), "active", false);
		when(items.findByUserIdOrderByIdAsc(1L)).thenReturn(List.of(owned(1L, HEAD, true), inactive));

		var response = service.getItems(1L, null);
		assertThat(response).extracting(r -> r.userItemId()).containsExactly(1L, 2L);
		assertThat(response.getFirst().equipped()).isTrue();
		assertThat(response.getLast().equipped()).isFalse();
		assertThat(response.getLast().assetKey()).isEqualTo("asset_2");
	}

	@Test
	void filtersUsingCatalogSlotIncludingUnequippedItems() {
		when(items.findByUserIdAndItemSlotTypeOrderByIdAsc(1L, UPPER_BODY))
				.thenReturn(List.of(owned(2L, UPPER_BODY, false)));
		assertThat(service.getItems(1L, "UPPER_BODY")).hasSize(1);
		verify(items, never()).findByUserIdOrderByIdAsc(anyLong());
	}

	@ParameterizedTest
	@ValueSource(strings = {"", " ", "WALL", "FLOOR", "HAT", "upper_body"})
	void rejectsInvalidSlot(String slot) {
		assertThatThrownBy(() -> service.getItems(1L, slot))
				.isInstanceOfSatisfying(BusinessException.class,
						e -> assertThat(e.getErrorCode()).isEqualTo(CommonErrorCode.INVALID_INPUT_VALUE));
		verifyNoInteractions(items);
	}

	@Test
	void clearsOldSlotBeforeEquippingAndReturnsSortedFullEquipment() {
		UserItem previous = owned(10L, UPPER_BODY, true);
		UserItem target = owned(2L, UPPER_BODY, false);
		UserItem hat = owned(5L, HEAD, true);
		when(items.findByIdAndUserId(2L, 1L)).thenReturn(Optional.of(target));
		when(items.findByUserIdAndEquippedSlot(1L, UPPER_BODY)).thenReturn(Optional.of(previous));
		when(items.findByUserIdAndEquippedSlotIsNotNull(1L)).thenReturn(List.of(target, hat));
		doAnswer(invocation -> {
			assertThat(previous.isEquipped()).isFalse();
			assertThat(target.isEquipped()).isFalse();
			return null;
		}).doNothing().when(items).flush();

		var response = service.updateEquipment(1L, 2L, true);
		assertThat(target.getEquippedSlot()).isEqualTo(UPPER_BODY);
		assertThat(response.equipped()).extracting(EquippedItemResponse::userItemId).containsExactly(5L, 2L);
		var order = inOrder(users, items);
		order.verify(users).findActiveByIdForUpdate(1L);
		order.verify(items).findByIdAndUserId(2L, 1L);
		order.verify(items).findByUserIdAndEquippedSlot(1L, UPPER_BODY);
		order.verify(items, times(2)).flush();
		order.verify(items).findByUserIdAndEquippedSlotIsNotNull(1L);
	}

	@Test
	void alreadyEquippedRequestReturnsEquipmentWithoutChangingIt() {
		UserItem target = owned(2L, HEAD, true);
		when(items.findByIdAndUserId(2L, 1L)).thenReturn(Optional.of(target));
		when(items.findByUserIdAndEquippedSlotIsNotNull(1L)).thenReturn(List.of(target));
		assertThat(service.updateEquipment(1L, 2L, true).equipped()).hasSize(1);
		verify(items, never()).flush();
		verify(items, never()).findByUserIdAndEquippedSlot(anyLong(), any());
	}

	@Test
	void staleUnequipDoesNotRemoveReplacementInSameSlot() {
		UserItem old = owned(2L, UPPER_BODY, false);
		UserItem replacement = owned(3L, UPPER_BODY, true);
		when(items.findByIdAndUserId(2L, 1L)).thenReturn(Optional.of(old));
		when(items.findByUserIdAndEquippedSlotIsNotNull(1L)).thenReturn(List.of(replacement));
		assertThat(service.updateEquipment(1L, 2L, false).equipped()).extracting(EquippedItemResponse::userItemId)
				.containsExactly(3L);
		assertThat(replacement.isEquipped()).isTrue();
		verify(items, never()).flush();
	}

	@Test
	void removesLastClothingAndReturnsEmptyEquipment() {
		UserItem target = owned(2L, LOWER_BODY, true);
		when(items.findByIdAndUserId(2L, 1L)).thenReturn(Optional.of(target));
		when(items.findByUserIdAndEquippedSlotIsNotNull(1L)).thenReturn(List.of());
		assertThat(service.updateEquipment(1L, 2L, false).equipped()).isEmpty();
		assertThat(target.isEquipped()).isFalse();
		verify(items).flush();
	}

	@Test
	void missingOrForeignItemReturnsSameError() {
		for (boolean equipped : List.of(true, false)) {
			assertThatThrownBy(() -> service.updateEquipment(1L, 99L, equipped))
					.isInstanceOfSatisfying(BusinessException.class,
							e -> assertThat(e.getErrorCode()).isEqualTo(ItemErrorCode.USER_ITEM_NOT_FOUND));
		}
		verify(items, never()).flush();
	}

	@Test
	void allOperationsRejectMissingOrDeletedUsers() {
		assertThatThrownBy(() -> service.getItems(9L, null)).isInstanceOfSatisfying(BusinessException.class,
				e -> assertThat(e.getErrorCode()).isEqualTo(UserErrorCode.USER_NOT_FOUND));
		assertThatThrownBy(() -> service.getEquipment(9L)).isInstanceOf(BusinessException.class);
		assertThatThrownBy(() -> service.updateEquipment(9L, 1L, true)).isInstanceOf(BusinessException.class);
		assertThatThrownBy(() -> service.updateEquipment(9L, 1L, false)).isInstanceOf(BusinessException.class);
		verifyNoInteractions(items);
	}
}
