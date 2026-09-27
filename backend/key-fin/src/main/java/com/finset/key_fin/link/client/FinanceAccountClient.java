package com.finset.key_fin.link.client;

import com.finset.key_fin.link.dto.response.FinanceAccount;

import java.util.List;

public interface FinanceAccountClient {

	List<FinanceAccount> findAccounts(String userKey);
}
