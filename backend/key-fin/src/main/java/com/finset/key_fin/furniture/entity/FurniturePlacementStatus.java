package com.finset.key_fin.furniture.entity;

import com.fasterxml.jackson.annotation.JsonCreator;

public enum FurniturePlacementStatus {
	FLOOR,
	LEFT_WALL,
	RIGHT_WALL;

	@JsonCreator(mode = JsonCreator.Mode.DELEGATING)
	public static FurniturePlacementStatus fromJson(String value) {
		return valueOf(value);
	}
}
