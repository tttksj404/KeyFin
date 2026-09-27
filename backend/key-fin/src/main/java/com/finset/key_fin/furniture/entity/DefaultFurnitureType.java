package com.finset.key_fin.furniture.entity;

import java.math.BigDecimal;

public enum DefaultFurnitureType {

	// Match frontend DEFAULT_CELLS / cellAnchor, rounded to the API's three decimal places.
	SOFA("198.125", "443.250"),
	TV("190.625", "334.688"),
	DINING_TABLE("64.604", "362.438"),
	COFFEE_TABLE("127.417", "429.875");

	private final BigDecimal initialX;
	private final BigDecimal initialY;

	DefaultFurnitureType(String initialX, String initialY) {
		this.initialX = new BigDecimal(initialX);
		this.initialY = new BigDecimal(initialY);
	}

	public void placeInitially(UserFurniture furniture) {
		furniture.place(FurniturePlacementStatus.FLOOR, FurniturePlacementDirection.FRONT_RIGHT,
				initialX, initialY, 0);
	}
}
