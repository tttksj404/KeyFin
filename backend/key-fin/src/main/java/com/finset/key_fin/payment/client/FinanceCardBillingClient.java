package com.finset.key_fin.payment.client;

import java.time.YearMonth;
import java.util.List;
import com.finset.key_fin.payment.dto.response.FinanceBillingStatement;

public interface FinanceCardBillingClient {

	List<FinanceBillingStatement> findBillingStatements(
			String userKey, String cardNo, String cvc, YearMonth from, YearMonth to);
}
