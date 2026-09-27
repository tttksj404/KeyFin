package com.finset.key_fin.coaching.dto;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

import tools.jackson.databind.json.JsonMapper;

class FdtSnapshotJsonTest {

	/** 코칭 snapshot.json 은 계좌에 추가 필드를 거부하므로(additionalProperties:false) 정확히 세 필드만 나가야 한다. */
	@Test
	void 계좌는_account_id_balance_krw_is_income_세_필드만_직렬화한다() {
		String json = JsonMapper.builder().build().writeValueAsString(new FdtSnapshot.Account("1", 1_000L, true));

		assertThat(json).isEqualTo("{\"account_id\":\"1\",\"balance_krw\":1000,\"is_income\":true}");
	}
}
