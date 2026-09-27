package com.finset.key_fin.item.entity;

public enum ItemSlotType {
	HEAD,
	FACE,
	UPPER_BODY,
	LOWER_BODY,
	SOCKS,
	FOOTWEAR,
	WALL,
	FLOOR;

	public boolean isAvatarSlot() {
		return this != WALL && this != FLOOR;
	}
}
