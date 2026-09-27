package com.finset.key_fin.transaction.entity;

import com.finset.key_fin.user.entity.User;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class TransactionSyncStateTest {

	@Test
	void 최초_동기화_상태는_마지막_동기화_시각이_없다() {
		User user = User.create("qwer@qwer.com", "password", "김예린");

		TransactionSyncState state = TransactionSyncState.create(
				user, TransactionAssetType.ACCOUNT, 1L);

		assertThat(state.getUser()).isSameAs(user);
		assertThat(state.getAssetType()).isEqualTo(TransactionAssetType.ACCOUNT);
		assertThat(state.getAssetId()).isEqualTo(1L);
		assertThat(state.getLastSyncedAt()).isNull();
	}

	@Test
	void 동기화이_성공하면_마지막_동기화_시각을_변경한다() {
		User user = User.create("qwer@qwer.com", "password", "김예린");
		TransactionSyncState state = TransactionSyncState.create(
				user, TransactionAssetType.CARD, 7L);
		LocalDateTime syncedAt = LocalDateTime.of(2026, 9, 15, 10, 30);

		state.recordSyncSuccess(syncedAt);

		assertThat(state.getLastSyncedAt()).isEqualTo(syncedAt);
	}

	@Test
	void 자산_ID는_양수여야_한다() {
		User user = User.create("qwer@qwer.com", "password", "김예린");

		assertThatThrownBy(() -> TransactionSyncState.create(
				user, TransactionAssetType.ACCOUNT, 0L))
				.isInstanceOf(IllegalArgumentException.class)
				.hasMessage("assetId must be positive");
	}
}

