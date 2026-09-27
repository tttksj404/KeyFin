package com.finset.key_fin.link.client;

import com.finset.key_fin.link.dto.response.FinanceCard;

import java.util.List;

public interface FinanceCardClient {

	List<FinanceCard> findCards(String userKey);
}
