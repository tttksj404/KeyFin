package com.finset.key_fin.transaction.client;

import com.finset.key_fin.transaction.dto.finance.response.FinanceAccountTransaction;

import java.time.LocalDate;
import java.util.List;

public interface FinanceAccountTransactionClient {

	List<FinanceAccountTransaction> findTransactions(
			String userKey,
			String accountNo,
			LocalDate startDate,
			LocalDate endDate
	);
}
