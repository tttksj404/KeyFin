package com.finset.key_fin.furniture.entity;

import com.fasterxml.jackson.annotation.JsonCreator;

public enum FurniturePlacementDirection {
	FRONT_LEFT,
	FRONT_RIGHT;

	@JsonCreator(mode = JsonCreator.Mode.DELEGATING)
	public static FurniturePlacementDirection fromJson(String value) {
		return valueOf(value);
	}
}
