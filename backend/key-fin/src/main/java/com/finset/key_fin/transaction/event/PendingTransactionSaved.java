package com.finset.key_fin.transaction.event;

public record PendingTransactionSaved(
		long userId,
		long transactionId,
		String merchantName,
		long amount
) {
}
