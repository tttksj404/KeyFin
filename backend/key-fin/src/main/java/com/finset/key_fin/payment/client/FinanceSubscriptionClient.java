package com.finset.key_fin.payment.client;

import java.util.List;

import com.finset.key_fin.payment.dto.response.FinanceSubscription;

public interface FinanceSubscriptionClient {

	List<FinanceSubscription> findSubscriptions(String userKey);
}
