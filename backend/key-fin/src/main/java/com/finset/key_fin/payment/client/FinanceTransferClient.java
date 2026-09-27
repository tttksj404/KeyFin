package com.finset.key_fin.payment.client;

import com.finset.key_fin.payment.dto.response.FinanceTransferResult;

public interface FinanceTransferClient {

	FinanceTransferResult transfer(
			String userKey, String transactionUniqueNo, String withdrawalAccountNo, String depositAccountNo,
			long amount, String summary);
}
