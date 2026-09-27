package com.finset.key_fin.furniture;

import com.finset.key_fin.furniture.dto.request.FurniturePlacementUpdateRequest;
import com.finset.key_fin.furniture.entity.FurniturePlacementDirection;
import com.finset.key_fin.furniture.entity.FurniturePlacementStatus;
import com.finset.key_fin.furniture.entity.UserFurniture;
import com.finset.key_fin.item.entity.Item;
import com.finset.key_fin.item.entity.ItemCategory;
import com.finset.key_fin.item.entity.ItemSlotType;
import com.finset.key_fin.user.entity.User;
import org.springframework.beans.BeanUtils;
import org.springframework.test.util.ReflectionTestUtils;

import java.math.BigDecimal;

public final class FurnitureFixtures {
	private FurnitureFixtures() {}

	public static UserFurniture owned(long id, ItemSlotType slot) {
		Item item = BeanUtils.instantiateClass(Item.class);
		ReflectionTestUtils.setField(item, "id", id + 100);
		ReflectionTestUtils.setField(item, "itemCategory", ItemCategory.FURNITURE);
		ReflectionTestUtils.setField(item, "slotType", slot);
		ReflectionTestUtils.setField(item, "name", "가구 " + id);
		ReflectionTestUtils.setField(item, "assetKey", "furniture_" + id);
		UserFurniture furniture = BeanUtils.instantiateClass(UserFurniture.class);
		ReflectionTestUtils.setField(furniture, "id", id);
		ReflectionTestUtils.setField(furniture, "item", item);
		ReflectionTestUtils.setField(furniture, "user", User.create("furniture@test.io", "hash", "가구 소유자"));
		return furniture;
	}

	public static FurniturePlacementUpdateRequest placement(FurniturePlacementStatus status) {
		return new FurniturePlacementUpdateRequest(true, status, FurniturePlacementDirection.FRONT_RIGHT,
				new BigDecimal("165.123"), new BigDecimal("280.456"), -2);
	}

	public static FurniturePlacementUpdateRequest removal() {
		return new FurniturePlacementUpdateRequest(false, null, null, null, null, null);
	}

	public static final String PLACEMENT_JSON = """
			{"placed":true,"placementStatus":"FLOOR","placementDirection":"FRONT_RIGHT",
			 "positionX":165.123,"positionY":280.456,"layer":-2}
			""";
}
