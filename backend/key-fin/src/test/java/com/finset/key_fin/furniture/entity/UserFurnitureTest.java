package com.finset.key_fin.furniture.entity;

import com.finset.key_fin.furniture.exception.FurnitureErrorCode;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.item.entity.ItemSlotType;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import java.math.BigDecimal;

import static com.finset.key_fin.furniture.FurnitureFixtures.owned;
import static org.assertj.core.api.Assertions.*;

class UserFurnitureTest {
	@ParameterizedTest
	@CsvSource({"FLOOR,FLOOR,FRONT_LEFT", "FLOOR,FLOOR,FRONT_RIGHT", "WALL,LEFT_WALL,FRONT_LEFT", "WALL,RIGHT_WALL,FRONT_RIGHT"})
	void placesMovesAndRepeatedlyRemovesWithoutLosingOwnership(ItemSlotType slot, FurniturePlacementStatus status,
			FurniturePlacementDirection direction) {
		var furniture = owned(1L, slot);
		var item = furniture.getItem();
		var user = furniture.getUser();
		assertThat(furniture.isPlaced()).isFalse();
		furniture.place(status, direction, new BigDecimal("165.123"), new BigDecimal("280.456"), -2);
		assertThat(furniture.isPlaced()).isTrue();
		assertThat(furniture.getPlacementStatus()).isEqualTo(status);
		assertThat(furniture.getPlacementDirection()).isEqualTo(direction);
		assertThat(furniture.getLayer()).isEqualTo(-2);
		furniture.place(status, direction, BigDecimal.ZERO, new BigDecimal("404"), 3);
		assertThat(furniture.getPositionX()).isEqualByComparingTo("0");
		assertThat(furniture.getPositionY()).isEqualByComparingTo("404");
		furniture.unplace();
		furniture.unplace();
		assertThat(furniture.isPlaced()).isFalse();
		assertThat(furniture.getPlacementStatus()).isNull();
		assertThat(furniture.getPlacementDirection()).isNull();
		assertThat(furniture.getPositionX()).isNull();
		assertThat(furniture.getPositionY()).isNull();
		assertThat(furniture.getLayer()).isZero();
		assertThat(furniture.getId()).isEqualTo(1L);
		assertThat(furniture.getItem()).isSameAs(item);
		assertThat(furniture.getUser()).isSameAs(user);
	}

	@ParameterizedTest
	@CsvSource({"FLOOR,LEFT_WALL", "FLOOR,RIGHT_WALL", "WALL,FLOOR"})
	void rejectsWrongSurfaceWithoutChangingExistingPlacement(ItemSlotType slot, FurniturePlacementStatus invalid) {
		var furniture = owned(1L, slot);
		var previous = slot == ItemSlotType.FLOOR ? FurniturePlacementStatus.FLOOR : FurniturePlacementStatus.LEFT_WALL;
		furniture.place(previous, FurniturePlacementDirection.FRONT_LEFT, BigDecimal.ONE, BigDecimal.TEN, -1);
		assertThatThrownBy(() -> furniture.place(invalid, FurniturePlacementDirection.FRONT_RIGHT,
				BigDecimal.ZERO, BigDecimal.ZERO, 0)).isInstanceOfSatisfying(BusinessException.class,
				e -> assertThat(e.getErrorCode()).isEqualTo(FurnitureErrorCode.PLACEMENT_NOT_ALLOWED));
		assertThat(furniture.getPlacementStatus()).isEqualTo(previous);
		assertThat(furniture.getPositionX()).isEqualByComparingTo("1");
		assertThat(furniture.getLayer()).isEqualTo(-1);
	}
}
