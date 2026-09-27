package com.finset.key_fin.coaching.dto;

import java.time.LocalDateTime;
import java.util.List;

public record ChatHistoryResponse(
		List<Entry> messages,
		LocalDateTime expiresAt
) {
	public record Entry(String role, String content, String chartId) {
	}

	public static ChatHistoryResponse empty() {
		return new ChatHistoryResponse(List.of(), null);
	}
}
