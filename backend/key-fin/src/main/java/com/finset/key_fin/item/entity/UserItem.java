package com.finset.key_fin.item.entity;

import com.finset.key_fin.user.entity.User;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.Generated;
import org.hibernate.generator.EventType;

import java.time.LocalDateTime;
import java.util.Objects;

@Getter
@Entity
@Table(name = "user_items")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class UserItem {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@ManyToOne(fetch = FetchType.LAZY, optional = false)
	@JoinColumn(name = "user_id", nullable = false)
	private User user;

	@ManyToOne(fetch = FetchType.LAZY, optional = false)
	@JoinColumn(name = "item_id", nullable = false)
	private Item item;

	@Enumerated(EnumType.STRING)
	@Column(name = "equipped_slot", length = 20)
	private ItemSlotType equippedSlot;

	@Generated(event = EventType.INSERT)
	@Enumerated(EnumType.STRING)
	@Column(name = "item_category", nullable = false, insertable = false, updatable = false, length = 20)
	private ItemCategory itemCategory;

	@Generated(event = EventType.INSERT)
	@Column(name = "acquired_at", nullable = false, insertable = false, updatable = false)
	private LocalDateTime acquiredAt;

	public static UserItem acquire(User user, Item item) {
		Objects.requireNonNull(user, "user must not be null");
		Objects.requireNonNull(item, "item must not be null");
		if (item.getItemCategory() != ItemCategory.AVATAR) {
			throw new IllegalArgumentException("아바타 아이템만 보유할 수 있습니다.");
		}
		UserItem userItem = new UserItem();
		userItem.user = user;
		userItem.item = item;
		return userItem;
	}

	public void equip() {
		this.equippedSlot = item.getSlotType();
	}

	public void unequip() {
		this.equippedSlot = null;
	}

	public boolean isEquipped() {
		return equippedSlot != null;
	}
}
