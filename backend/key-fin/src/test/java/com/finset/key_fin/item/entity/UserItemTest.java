package com.finset.key_fin.item.entity;

import com.finset.key_fin.item.ItemFixtures;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

import static org.assertj.core.api.Assertions.assertThat;

class UserItemTest {
	@ParameterizedTest
	@EnumSource(value = ItemSlotType.class, names = {"WALL", "FLOOR"}, mode = EnumSource.Mode.EXCLUDE)
	void equipsFromCatalogSlotAndAllowsRepeatedRemovalForEveryAvatarPart(ItemSlotType slot) {
		UserItem owned = ItemFixtures.owned(1L, slot, false);
		assertThat(owned.isEquipped()).isFalse();
		owned.equip();
		owned.equip();
		assertThat(owned.getEquippedSlot()).isEqualTo(slot);
		assertThat(owned.isEquipped()).isTrue();

		owned.unequip();
		owned.unequip();
		assertThat(owned.getEquippedSlot()).isNull();
		assertThat(owned.isEquipped()).isFalse();
		assertThat(owned.getId()).isEqualTo(1L);
		assertThat(owned.getItem()).isNotNull();
	}
}
