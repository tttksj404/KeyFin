package com.finset.key_fin.transaction.repository;

import java.time.LocalDate;

public record TransactionSearchCondition(
		long userId,
		LocalDate startDate,
		LocalDate endDate,
		Integer envelopeId,
		Integer subcategoryId,
		Long accountId,
		Long cardId,
		Long cursor,
		int limit
) {
}
