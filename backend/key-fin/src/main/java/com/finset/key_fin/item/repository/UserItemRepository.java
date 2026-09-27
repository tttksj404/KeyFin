package com.finset.key_fin.item.repository;

import com.finset.key_fin.item.entity.ItemSlotType;
import com.finset.key_fin.item.entity.UserItem;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface UserItemRepository extends JpaRepository<UserItem, Long> {
	boolean existsByUserIdAndItemId(Long userId, Long itemId);

	@Query("select ui.item.id from UserItem ui where ui.user.id = :userId")
	List<Long> findOwnedItemIds(@Param("userId") Long userId);

	@EntityGraph(attributePaths = "item")
	List<UserItem> findByUserIdOrderByIdAsc(Long userId);

	@EntityGraph(attributePaths = "item")
	List<UserItem> findByUserIdAndItemSlotTypeOrderByIdAsc(Long userId, ItemSlotType slotType);

	@EntityGraph(attributePaths = "item")
	Optional<UserItem> findByIdAndUserId(Long id, Long userId);

	@EntityGraph(attributePaths = "item")
	List<UserItem> findByUserIdAndEquippedSlotIsNotNull(Long userId);

	Optional<UserItem> findByUserIdAndEquippedSlot(Long userId, ItemSlotType equippedSlot);
}
