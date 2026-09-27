package com.finset.key_fin.payment.dto.response;

import java.time.LocalDateTime;
import java.util.List;
import com.finset.key_fin.payment.entity.AuditLog;
import com.finset.key_fin.payment.entity.AuditLog.AuditAction;

public record TransferDetailResponse(
		TransferResponse transfer,
		List<HistoryEntry> history
) {
	public static TransferDetailResponse of(TransferResponse transfer, List<AuditLog> logs) {
		return new TransferDetailResponse(transfer, logs.stream()
				.map(log -> new HistoryEntry(log.getAction(), log.getBasis(), log.getCreatedAt()))
				.toList());
	}

	public record HistoryEntry(AuditAction action, String basis, LocalDateTime at) {
	}
}
