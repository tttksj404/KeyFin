package com.finset.key_fin.item.entity;

import com.finset.key_fin.furniture.entity.DefaultFurnitureType;
import com.finset.key_fin.furniture.entity.FurnitureType;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Entity
@Table(name = "items")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Item {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@Enumerated(EnumType.STRING)
	@Column(name = "item_category", nullable = false, length = 20)
	private ItemCategory itemCategory;

	@Enumerated(EnumType.STRING)
	@Column(name = "slot_type", nullable = false, length = 20)
	private ItemSlotType slotType;

	@Column(nullable = false, length = 50)
	private String name;

	@Column(nullable = false)
	private Integer price;

	@Column(name = "asset_key", nullable = false, length = 100)
	private String assetKey;

	@Column(name = "theme_code", length = 30)
	private String themeCode;

	@Enumerated(EnumType.STRING)
	@Column(name = "default_furniture_type", length = 20)
	private DefaultFurnitureType defaultFurnitureType;

	@Enumerated(EnumType.STRING)
	@Column(name = "furniture_type", length = 20)
	private FurnitureType furnitureType;

	@Column(name = "is_active", nullable = false)
	private boolean active = true;
}
