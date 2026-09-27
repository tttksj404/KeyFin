package com.finset.key_fin.link.client;

import com.finset.key_fin.link.dto.response.FinanceMember;

public interface FinanceMemberClient {

	FinanceMember findByEmail(String email);
}
