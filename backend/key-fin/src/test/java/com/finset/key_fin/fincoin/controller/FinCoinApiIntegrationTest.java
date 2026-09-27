package com.finset.key_fin.fincoin.controller;

import com.finset.key_fin.auth.config.JwtProperties;
import com.finset.key_fin.auth.jwt.JwtTokenProvider;
import com.finset.key_fin.support.SpringIntegrationTestSupport;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.LocalDate;
import java.util.List;

import static org.hamcrest.Matchers.aMapWithSize;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@Transactional
@Sql("/sql/fin-coin-history-fixture.sql")
class FinCoinApiIntegrationTest extends SpringIntegrationTestSupport {

	private static final String HISTORY_PATH = "/api/v1/fin-coins";
	private static final String BALANCE_PATH = "/api/v1/fin-coins/balance";

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JwtTokenProvider jwtTokenProvider;

	@Autowired
	private JwtProperties jwtProperties;

	@Autowired
	private Clock clock;

	@Autowired
	private JdbcClient jdbcClient;

	@Test
	void returnsOnlyTokenOwnersHistoryWithRealAuthenticationAndDatabase() throws Exception {
		mockMvc.perform(authenticatedRequest(HISTORY_PATH, 981L).param("userId", "982").param("size", "2"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.success").value(true))
				.andExpect(jsonPath("$.code").value("SUCCESS"))
				.andExpect(jsonPath("$.data").value(aMapWithSize(2)))
				.andExpect(jsonPath("$.data.balance").doesNotHaveJsonPath())
				.andExpect(jsonPath("$.data.items").value(hasSize(2)))
				.andExpect(jsonPath("$.data.items[0].id").value(8_100_000_009L))
				.andExpect(jsonPath("$.data.items[0].delta").value(-150))
				.andExpect(jsonPath("$.data.items[0].balanceAfter").value(700))
				.andExpect(jsonPath("$.data.items[0].reasonCode").value("PURCHASE"))
				.andExpect(jsonPath("$.data.items[0].reasonText").value("아이템 구매"))
				.andExpect(jsonPath("$.data.items[0].grantDate").value("2026-09-02"))
				.andExpect(jsonPath("$.data.items[1].id").value(8_100_000_007L))
				.andExpect(jsonPath("$.data.nextCursor").value(8_100_000_007L));

		mockMvc.perform(authenticatedRequest(HISTORY_PATH, 981L).param("cursor", "8100000003"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.items").value(hasSize(1)))
				.andExpect(jsonPath("$.data.items[0].id").value(8_100_000_001L))
				.andExpect(jsonPath("$.data.nextCursor").hasJsonPath())
				.andExpect(jsonPath("$.data.nextCursor").value(nullValue()));
	}

	@ParameterizedTest
	@CsvSource({"981, 700", "982, 2000", "983, 0"})
	void returnsLatestBalanceForTokenOwnerIncludingEmptyHistory(long userId, int balance) throws Exception {
		mockMvc.perform(authenticatedRequest(BALANCE_PATH, userId).param("userId", "984"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data").value(aMapWithSize(1)))
				.andExpect(jsonPath("$.data.balance").value(balance));
	}

	@Test
	void returnsExplicitNullCursorForEmptyHistory() throws Exception {
		mockMvc.perform(authenticatedRequest(HISTORY_PATH, 983L))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data").value(aMapWithSize(2)))
				.andExpect(jsonPath("$.data.balance").doesNotHaveJsonPath())
				.andExpect(jsonPath("$.data.items").isEmpty())
				.andExpect(jsonPath("$.data.nextCursor").hasJsonPath())
				.andExpect(jsonPath("$.data.nextCursor").value(nullValue()));
	}

	@Test
	void honorsDefaultAndMaximumSizesWhenMoreThanOneHundredRowsExist() throws Exception {
		long firstId = 8_100_001_000L;
		for (int index = 0; index < 101; index++) {
			jdbcClient.sql("""
					INSERT INTO fin_coin (id, user_id, delta, balance_after, reason_code, grant_date)
					VALUES (:id, 983, 1, :balance, 'ATTEND', :date)
					""")
					.param("id", firstId + index)
					.param("balance", index + 1)
					.param("date", LocalDate.of(2026, 1, 1).plusDays(index))
					.update();
		}

		mockMvc.perform(authenticatedRequest(HISTORY_PATH, 983L))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.items").value(hasSize(20)))
				.andExpect(jsonPath("$.data.items[0].id").value(firstId + 100))
				.andExpect(jsonPath("$.data.nextCursor").value(firstId + 81));

		mockMvc.perform(authenticatedRequest(HISTORY_PATH, 983L).param("size", "100"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.items").value(hasSize(100)))
				.andExpect(jsonPath("$.data.nextCursor").value(firstId + 1));

		mockMvc.perform(authenticatedRequest(HISTORY_PATH, 983L)
						.param("size", "100").param("cursor", Long.toString(firstId + 1)))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.items").value(hasSize(1)))
				.andExpect(jsonPath("$.data.items[0].id").value(firstId))
				.andExpect(jsonPath("$.data.nextCursor").hasJsonPath())
				.andExpect(jsonPath("$.data.nextCursor").value(nullValue()));
	}

	@ParameterizedTest
	@ValueSource(longs = {984, 985})
	void rejectsDeletedOrMissingUsersEvenWithValidTokens(long userId) throws Exception {
		for (String path : List.of(HISTORY_PATH, BALANCE_PATH)) {
			mockMvc.perform(authenticatedRequest(path, userId))
					.andExpect(status().isNotFound())
					.andExpect(jsonPath("$.success").value(false))
					.andExpect(jsonPath("$.code").value("USER_001"));
		}
	}

	@ParameterizedTest
	@ValueSource(strings = {HISTORY_PATH, BALANCE_PATH})
	void rejectsMissingMalformedExpiredAndRefreshTokens(String path) throws Exception {
		Clock expiredClock = Clock.fixed(
				clock.instant().minus(jwtProperties.accessTokenExpiration()).minusSeconds(60), clock.getZone());
		String expiredToken = new JwtTokenProvider(jwtProperties, expiredClock).generateAccessToken(981L);

		mockMvc.perform(get(path))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("AUTH_005"));
		mockMvc.perform(get(path).header("Authorization", "Bearer not-a-jwt"))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("AUTH_002"));
		mockMvc.perform(get(path).header("Authorization", "Bearer " + expiredToken))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("AUTH_003"));
		mockMvc.perform(get(path).header("Authorization", "Bearer " + jwtTokenProvider.generateRefreshToken(981L)))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("AUTH_002"));
	}

	private MockHttpServletRequestBuilder authenticatedRequest(String path, long userId) {
		return get(path).header("Authorization", "Bearer " + jwtTokenProvider.generateAccessToken(userId));
	}
}
