package com.finset.key_fin.transaction.dto.response;

import com.finset.key_fin.transaction.entity.ConfirmStatus;
import com.finset.key_fin.transaction.entity.ExcludeTag;
import com.finset.key_fin.transaction.entity.Transaction;
import io.swagger.v3.oas.annotations.media.Schema;

public record TransactionClassificationResponse(
		@Schema(description = "거래 ID", example = "501") Long transactionId,
		@Schema(description = "세분류 ID", example = "102", nullable = true) Integer subcategoryId,
		@Schema(description = "예산 제외 태그", example = "NONE") ExcludeTag excludeTag,
		@Schema(description = "더치페이 실제 부담액", example = "15000", nullable = true) Long adjustedAmount,
		@Schema(description = "분류 확정 상태", example = "CONFIRMED") ConfirmStatus confirmStatus
) {
	public static TransactionClassificationResponse from(Transaction transaction) {
		return new TransactionClassificationResponse(
				transaction.getId(),
				transaction.getSubcategoryId(),
				transaction.getExcludeTag(),
				transaction.getAdjustedAmount(),
				transaction.getConfirmStatus()
		);
	}
}
