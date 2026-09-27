package com.finset.key_fin.room.repository;

import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;

@Repository
@RequiredArgsConstructor
public class RoomStickerRepository {
	private final JdbcClient jdbc;

	public boolean wasApplied(long budgetId) {
		return jdbc.sql("SELECT EXISTS(SELECT 1 FROM budget_sticker_applications WHERE budget_id = :id)")
				.param("id", budgetId).query(Boolean.class).single();
	}

	public void recordApplication(long userId, long budgetId, LocalDateTime appliedAt) {
		jdbc.sql("INSERT INTO budget_sticker_applications (user_id, budget_id, applied_at) VALUES (:user, :budget, :at)")
				.param("user", userId).param("budget", budgetId).param("at", appliedAt).update();
	}

	/** Reset only the recovered budget; manual sticker removal keeps the application marker. */
	public void clearApplication(long budgetId) {
		jdbc.sql("DELETE FROM budget_sticker_applications WHERE budget_id = :id")
				.param("id", budgetId).update();
	}
}
