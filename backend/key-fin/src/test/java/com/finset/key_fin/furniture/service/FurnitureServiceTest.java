package com.finset.key_fin.furniture.service;

import com.finset.key_fin.furniture.dto.request.FurniturePlacementUpdateRequest;
import com.finset.key_fin.furniture.dto.response.UserFurnitureResponse;
import com.finset.key_fin.furniture.entity.FurniturePlacementStatus;
import com.finset.key_fin.furniture.entity.FurnitureType;
import com.finset.key_fin.furniture.exception.FurnitureErrorCode;
import com.finset.key_fin.furniture.repository.UserFurnitureRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.exception.CommonErrorCode;
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
import java.util.Arrays;

import static com.finset.key_fin.furniture.FurnitureFixtures.*;
import static com.finset.key_fin.item.entity.ItemSlotType.*;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

class FurnitureServiceTest {
	private final UserFurnitureRepository furnitures = mock(UserFurnitureRepository.class);
	private final UserRepository users = mock(UserRepository.class);
	private final FurnitureService service = new FurnitureServiceImpl(furnitures, users);

	@BeforeEach
	void setUp() {
		var user = User.create("furniture@test.io", "hash", "가구 소유자");
		lenient().when(users.findByIdAndDeletedAtIsNull(1L)).thenReturn(Optional.of(user));
		lenient().when(users.findActiveByIdForUpdate(1L)).thenReturn(Optional.of(user));
	}

	@Test
	void listsOwnedFurnitureIncludingInactiveAndUnplacedEntries() {
		var first = owned(1, FLOOR);
		var second = owned(2, WALL);
		ReflectionTestUtils.setField(second.getItem(), "active", false);
		when(furnitures.findByUserIdOrderByIdAsc(1L)).thenReturn(List.of(first, second));
		assertThat(service.getFurnitures(1, null)).extracting(UserFurnitureResponse::userFurnitureId).containsExactly(1L, 2L);
		assertThat(service.getFurnitures(1, null)).allMatch(r -> !r.placed());
		when(furnitures.findByUserIdAndItemSlotTypeOrderByIdAsc(1L, WALL)).thenReturn(List.of(second));
		assertThat(service.getFurnitures(1, "WALL")).extracting(UserFurnitureResponse::userFurnitureId).containsExactly(2L);
		when(furnitures.findByUserIdAndItemSlotTypeOrderByIdAsc(1L, FLOOR)).thenReturn(List.of(first));
		assertThat(service.getFurnitures(1, "FLOOR")).hasSize(1);
	}

	@Test
	void emptyOwnershipAndPlacementReturnEmptyLists() {
		assertThat(service.getFurnitures(1, null)).isEmpty();
		assertThat(service.getPlacedFurnitures(1)).isEmpty();
	}

	@Test
	void changesInactiveOwnedFurnitureAfterLockingUserAndReturnsOnlyTarget() {
		var required = Arrays.stream(FurnitureType.values()).map(type -> {
			var furniture = owned(1000 + type.ordinal(), FLOOR);
			ReflectionTestUtils.setField(furniture.getItem(), "furnitureType", type);
			return furniture;
		}).toList();
		when(furnitures.findByUserIdAndPlacementStatusIsNotNullOrderByIdAsc(1L)).thenReturn(required);
		var target = owned(3, FLOOR);
		ReflectionTestUtils.setField(target.getItem(), "active", false);
		when(furnitures.findByIdAndUserId(3L, 1L)).thenReturn(Optional.of(target));
		var request = placement(FurniturePlacementStatus.FLOOR);
		var response = service.updatePlacement(1, 3, request);
		assertThat(response.userFurnitureId()).isEqualTo(3);
		assertThat(response.placed()).isTrue();
		assertThat(response.positionX()).isEqualByComparingTo("165.123");
		assertThat(response.layer()).isEqualTo(-2);
		var order = inOrder(users, furnitures);
		order.verify(users).findActiveByIdForUpdate(1L);
		order.verify(furnitures).findByIdAndUserId(3L, 1L);
		order.verify(furnitures).flush();
		assertThat(service.updatePlacement(1, 3, request)).isEqualTo(response);
		var defaultLayer = new FurniturePlacementUpdateRequest(true, request.placementStatus(),
				request.placementDirection(), request.positionX(), request.positionY(), null);
		assertThat(service.updatePlacement(1, 3, defaultLayer).layer()).isZero();
		assertThat(service.updatePlacement(1, 3, removal()).placed()).isFalse();
		assertThat(service.updatePlacement(1, 3, removal()).positionX()).isNull();
	}

	@Test
	void mapsPlacedFurnitureForRoom() {
		var furniture = owned(1, WALL);
		var request = placement(FurniturePlacementStatus.RIGHT_WALL);
		furniture.place(request.placementStatus(), request.placementDirection(), request.positionX(), request.positionY(), -2);
		when(furnitures.findByUserIdAndPlacementStatusIsNotNullOrderByIdAsc(1L)).thenReturn(List.of(furniture));
		var response = service.getPlacedFurnitures(1).getFirst();
		assertThat(response.userFurnitureId()).isEqualTo(1);
		assertThat(response.slotType()).isEqualTo(WALL);
		assertThat(response.placementStatus()).isEqualTo(FurniturePlacementStatus.RIGHT_WALL);
	}

	@ParameterizedTest
	@ValueSource(strings = {"", " ", "HEAD", "LEFT_WALL", "floor", "UNKNOWN"})
	void rejectsInvalidSlot(String slot) {
		assertThatThrownBy(() -> service.getFurnitures(1, slot)).isInstanceOfSatisfying(BusinessException.class,
				e -> assertThat(e.getErrorCode()).isEqualTo(CommonErrorCode.INVALID_INPUT_VALUE));
		verifyNoInteractions(furnitures);
	}

	@Test
	void foreignAndMissingFurnitureReturnSameErrorForPlacementAndRemoval() {
		for (var request : List.of(placement(FurniturePlacementStatus.FLOOR), removal())) {
			assertThatThrownBy(() -> service.updatePlacement(1, 999, request)).isInstanceOfSatisfying(BusinessException.class,
					e -> assertThat(e.getErrorCode()).isEqualTo(FurnitureErrorCode.USER_FURNITURE_NOT_FOUND));
		}
		verify(furnitures, never()).flush();
	}

	@Test
	void allOperationsRejectMissingOrDeletedUser() {
		assertThatThrownBy(() -> service.getFurnitures(9, null)).isInstanceOfSatisfying(BusinessException.class,
				e -> assertThat(e.getErrorCode()).isEqualTo(UserErrorCode.USER_NOT_FOUND));
		assertThatThrownBy(() -> service.getPlacedFurnitures(9)).isInstanceOf(BusinessException.class);
		assertThatThrownBy(() -> service.updatePlacement(9, 1, removal())).isInstanceOf(BusinessException.class);
		verifyNoInteractions(furnitures);
	}
}
