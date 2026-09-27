package com.finset.key_fin.payment.dto.response;

import java.time.LocalDate;
import java.time.LocalDateTime;
import com.finset.key_fin.payment.dto.response.PaymentCalendarResponse.CalendarItemType;
import com.finset.key_fin.payment.entity.PrepareTransfer;
import com.finset.key_fin.payment.entity.TransferStatus;

public record TransferResponse(
		Long id,
		TransferStatus status,
		LocalDate scheduledDate,
		LocalDate dueDate,
		long requiredAmount,
		Long fromAccountId,
		Long toAccountId,
		Purpose purpose,
		LocalDateTime executedAt,
		String failReason,
		LocalDateTime createdAt
) {
	public static TransferResponse of(PrepareTransfer transfer, String purposeName) {
		CalendarItemType type = transfer.getCardBillingId() != null ? CalendarItemType.CARD_BILL : CalendarItemType.FIXED;
		return new TransferResponse(
				transfer.getId(), transfer.getStatus(), transfer.getScheduledDate(), transfer.getDueDate(),
				transfer.getRequiredAmount(), transfer.getFromAccountId(), transfer.getToAccountId(),
				new Purpose(type, transfer.getFixedExpenseId(), transfer.getCardBillingId(), purposeName),
				transfer.getExecutedAt(), transfer.getFailReason(), transfer.getCreatedAt());
	}

	public record Purpose(CalendarItemType type, Long fixedExpenseId, Long cardBillingId, String name) {
	}
}
