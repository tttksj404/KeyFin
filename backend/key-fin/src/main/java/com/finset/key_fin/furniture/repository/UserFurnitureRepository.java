package com.finset.key_fin.furniture.repository;

import com.finset.key_fin.furniture.entity.UserFurniture;
import com.finset.key_fin.item.entity.ItemSlotType;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface UserFurnitureRepository extends JpaRepository<UserFurniture, Long> {
	boolean existsByUserIdAndItemId(Long userId, Long itemId);

	@Query("select uf.item.id from UserFurniture uf where uf.user.id = :userId")
	List<Long> findOwnedItemIds(@Param("userId") Long userId);

	@EntityGraph(attributePaths = "item")
	List<UserFurniture> findByUserIdOrderByIdAsc(Long userId);

	@EntityGraph(attributePaths = "item")
	List<UserFurniture> findByUserIdAndItemSlotTypeOrderByIdAsc(Long userId, ItemSlotType slotType);

	@EntityGraph(attributePaths = "item")
	Optional<UserFurniture> findByIdAndUserId(Long id, Long userId);

	@EntityGraph(attributePaths = "item")
	List<UserFurniture> findByUserIdAndPlacementStatusIsNotNullOrderByIdAsc(Long userId);
}
