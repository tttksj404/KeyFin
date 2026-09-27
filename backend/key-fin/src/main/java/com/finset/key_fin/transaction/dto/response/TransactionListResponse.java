package com.finset.key_fin.transaction.dto.response;

import com.finset.key_fin.transaction.entity.ConfirmStatus;
import com.finset.key_fin.transaction.entity.ExcludeTag;
import com.finset.key_fin.transaction.entity.TransactionStatus;
import com.finset.key_fin.transaction.entity.TransactionType;
import com.finset.key_fin.transaction.repository.TransactionQueryRow;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.LocalDate;
import java.time.LocalTime;
import java.util.List;

public record TransactionListResponse(
		@Schema(description = "거래 목록")
		List<TransactionItem> items,
		@Schema(description = "다음 페이지 cursor. 다음 페이지가 없으면 null", example = "481", nullable = true)
		Long nextCursor
) {

	public record TransactionItem(
			@Schema(description = "거래 ID", example = "501") Long id,
			@Schema(description = "거래 유형", example = "CARD") TransactionType txType,
			@Schema(description = "가맹점명 또는 거래 원문", example = "메가커피 역삼점", nullable = true) String merchantName,
			@Schema(description = "거래 금액(원)", example = "4500") Long amount,
			@Schema(description = "거래 일자", example = "2026-09-08") LocalDate txDate,
			@Schema(description = "거래 시각", example = "14:21:00") LocalTime txTime,
			@Schema(description = "봉투 ID", example = "1", nullable = true) Integer envelopeId,
			@Schema(description = "세분류 ID", example = "102", nullable = true) Integer subcategoryId,
			@Schema(description = "세분류명", example = "카페", nullable = true) String subcategoryName,
			@Schema(description = "분류 확정 상태", example = "AUTO") ConfirmStatus confirmStatus,
			@Schema(description = "예산 제외 태그", example = "NONE") ExcludeTag excludeTag,
			@Schema(description = "거래 상태", example = "NORMAL") TransactionStatus status,
			@Schema(description = "거래 메모", nullable = true) String memo,
			@Schema(description = "계좌 ID", nullable = true) Long accountId,
			@Schema(description = "카드 ID", nullable = true) Long cardId,
			@Schema(description = "차감 인정 금액", nullable = true) Long adjustedAmount
	) {
		public static TransactionItem from(TransactionQueryRow row) {
			return new TransactionItem(
					row.id(), row.transactionType(), row.merchantName(), row.amount(),
					row.transactionDate(), row.transactionTime(), row.envelopeId(),
					row.subcategoryId(), row.subcategoryName(), row.confirmStatus(),
					row.excludeTag(), row.status(), row.memo(), row.accountId(),
					row.cardId(), row.adjustedAmount()
			);
		}
	}
}
