package com.finset.key_fin.transaction.repository;

import com.finset.key_fin.transaction.entity.ConfirmStatus;
import com.finset.key_fin.transaction.entity.ExcludeTag;
import com.finset.key_fin.transaction.entity.TransactionStatus;
import com.finset.key_fin.transaction.entity.TransactionType;

import java.time.LocalDate;
import java.time.LocalTime;

public record TransactionQueryRow(
		Long id,
		TransactionType transactionType,
		String merchantName,
		Long amount,
		LocalDate transactionDate,
		LocalTime transactionTime,
		Integer envelopeId,
		Integer subcategoryId,
		String subcategoryName,
		ConfirmStatus confirmStatus,
		ExcludeTag excludeTag,
		TransactionStatus status,
		String memo,
		Long accountId,
		Long cardId,
		Long adjustedAmount
) {
}
