package com.finset.key_fin.transaction.client;

import com.finset.key_fin.transaction.dto.finance.response.FinanceCardTransaction;

import java.time.LocalDate;
import java.util.List;

public interface FinanceCardTransactionClient {

	List<FinanceCardTransaction> findTransactions(
			String userKey,
			String cardNo,
			String cvc,
			LocalDate startDate,
			LocalDate endDate
	);
}
