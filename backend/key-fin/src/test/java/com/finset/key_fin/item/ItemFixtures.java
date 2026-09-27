package com.finset.key_fin.item;

import com.finset.key_fin.item.entity.Item;
import com.finset.key_fin.item.entity.ItemCategory;
import com.finset.key_fin.item.entity.ItemSlotType;
import com.finset.key_fin.item.entity.UserItem;
import org.springframework.beans.BeanUtils;
import org.springframework.test.util.ReflectionTestUtils;

public final class ItemFixtures {
	private ItemFixtures() {
	}

	public static UserItem owned(long id, ItemSlotType slot, boolean equipped) {
		Item item = BeanUtils.instantiateClass(Item.class);
		ReflectionTestUtils.setField(item, "id", id + 1000);
		ReflectionTestUtils.setField(item, "name", "아이템 " + id);
		ReflectionTestUtils.setField(item, "assetKey", "asset_" + id);
		ReflectionTestUtils.setField(item, "itemCategory", ItemCategory.AVATAR);
		ReflectionTestUtils.setField(item, "slotType", slot);
		UserItem owned = BeanUtils.instantiateClass(UserItem.class);
		ReflectionTestUtils.setField(owned, "id", id);
		ReflectionTestUtils.setField(owned, "item", item);
		if (equipped) {
			owned.equip();
		}
		return owned;
	}
}
