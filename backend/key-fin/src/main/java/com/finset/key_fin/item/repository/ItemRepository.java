package com.finset.key_fin.item.repository;

import com.finset.key_fin.item.entity.Item;
import com.finset.key_fin.item.entity.ItemCategory;
import com.finset.key_fin.item.entity.ItemSlotType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;

public interface ItemRepository extends JpaRepository<Item, Long> {
	List<Item> findByDefaultFurnitureTypeIsNotNullOrderByIdAsc();

	@Query("""
			select i from Item i
			where i.active = true
			  and i.defaultFurnitureType is null
			  and (:category is null or i.itemCategory = :category)
			  and (:slotType is null or i.slotType = :slotType)
			order by i.id
			""")
	List<Item> findShopItems(@Param("category") ItemCategory category, @Param("slotType") ItemSlotType slotType);
}
