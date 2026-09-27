package com.finset.key_fin.fincoin.controller;

import com.finset.key_fin.fincoin.service.FinCoinService;
import com.finset.key_fin.auth.config.JwtProperties;
import com.finset.key_fin.auth.jwt.JwtTokenProvider;
import com.finset.key_fin.fincoin.entity.FinCoin;
import com.finset.key_fin.fincoin.entity.FinCoinReason;
import com.finset.key_fin.fincoin.repository.FinCoinRepository;
import com.finset.key_fin.support.SpringIntegrationTestSupport;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.repository.UserRepository;
import com.jayway.jsonpath.JsonPath;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.Primary;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.hamcrest.Matchers.aMapWithSize;
import static org.hamcrest.Matchers.containsInAnyOrder;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@Timeout(90)
class AttendanceApiIntegrationTest extends SpringIntegrationTestSupport {

	private static final String PATH = "/api/v1/fin-coins/attendance";
	private static final Instant NOW = Instant.parse("2026-09-11T03:00:00Z");
	private static final LocalDate TODAY = LocalDate.of(2026, 9, 11);
	private final List<Long> testUsers = new ArrayList<>();

	@Autowired private MockMvc mockMvc;
	@Autowired private UserRepository users;
	@Autowired private FinCoinRepository coins;
	@Autowired private JdbcClient jdbc;
	@Autowired private JwtTokenProvider tokens;
	@Autowired private JwtProperties jwtProperties;
	@Autowired private FinCoinService finCoinService;
	@Autowired private PlatformTransactionManager transactionManager;
	@Autowired private MockRestServiceServer financeServer;

	@BeforeEach
	void setUp() {
		testClock.set(NOW);
		financeServer.reset();
	}

	@AfterEach
	void cleanUp() {
		try {
			// 금융망 요청 기대값을 등록하지 않으므로 출석 중 외부 호출은 테스트 실패다.
			financeServer.verify();
		} finally {
			for (long userId : testUsers) {
				jdbc.sql("DELETE FROM fin_coin WHERE user_id = :id").param("id", userId).update();
				users.deleteById(userId);
			}
			testUsers.clear();
		}
	}

	@Test
	void grantsFirstAttendanceWithoutFinanceConnectionAndExposesLedger() throws Exception {
		long userId = createUser();
		assertThat(users.findById(userId).orElseThrow().isFinanceConnected()).isFalse();

		assertAttendance(userId, 10, 10);

		FinCoin coin = coins.findFirstByUserIdOrderByIdDesc(userId).orElseThrow();
		assertThat(coin.getReasonCode()).isEqualTo(FinCoinReason.ATTEND);
		assertThat(coin.getGrantDate()).isEqualTo(TODAY);
		assertThat(coin.getRefId()).isNull();
		assertThat(coin.getCreatedAt()).isNotNull();
		assertThat(attendanceCount(userId)).isEqualTo(1);
		mockMvc.perform(authenticated(get("/api/v1/fin-coins/balance"), userId))
				.andExpect(status().isOk()).andExpect(jsonPath("$.data.balance").value(10));
		mockMvc.perform(authenticated(get("/api/v1/fin-coins"), userId))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.items[0].reasonCode").value("ATTEND"))
				.andExpect(jsonPath("$.data.items[0].delta").value(10))
				.andExpect(jsonPath("$.data.items[0].balanceAfter").value(10));
	}

	@Test
	void addsRewardToExistingBalanceAndDoesNotRewardSameDayRetries() throws Exception {
		long userId = createUser();
		insertCoin(userId, 1250, 1250, "ATTEND", TODAY.minusDays(1));

		assertAttendance(userId, 10, 1260);
		assertAttendance(userId, 0, 1260);
		assertAttendance(userId, 0, 1260);
		assertThat(attendanceCount(userId)).isEqualTo(2);
	}

	@Test
	void duplicateReturnsLatestBalanceAfterAnotherCoinChange() throws Exception {
		long userId = createUser();
		assertAttendance(userId, 10, 10);
		insertCoin(userId, -7, 3, "PURCHASE", TODAY);

		assertAttendance(userId, 0, 3);
		assertThat(attendanceCount(userId)).isEqualTo(1);
	}

	@Test
	void anotherReasonTodayDoesNotPreventAttendance() throws Exception {
		long userId = createUser();
		insertCoin(userId, 50, 50, "CONFIRM_ALL", TODAY);

		assertAttendance(userId, 10, 60);
		assertThat(attendanceCount(userId)).isEqualTo(1);
	}

	@Test
	void resetsEligibilityAtKoreanMidnightEvenThoughClockUsesUtc() throws Exception {
		long userId = createUser();
		testClock.set(Instant.parse("2026-09-11T14:59:59Z"));
		assertAttendance(userId, 10, 10);
		assertAttendance(userId, 0, 10);

		testClock.set(Instant.parse("2026-09-11T15:00:00Z"));
		assertAttendance(userId, 10, 20);
		assertAttendance(userId, 0, 20);
		assertThat(coins.existsByUserIdAndGrantDateAndReasonCode(userId, TODAY, FinCoinReason.ATTEND)).isTrue();
		assertThat(coins.existsByUserIdAndGrantDateAndReasonCode(userId, TODAY.plusDays(1), FinCoinReason.ATTEND)).isTrue();
	}

	@Test
	void isolatesUsersAndIgnoresClientSuppliedIdentityDateAndAmount() throws Exception {
		long owner = createUser();
		long other = createUser();
		mockMvc.perform(authenticated(post(PATH), owner)
						.param("userId", Long.toString(other)).param("grantDate", "2099-01-01").param("amount", "1000")
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"userId\":" + other + ",\"grantDate\":\"2099-01-01\",\"amount\":1000}"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.granted").value(10))
				.andExpect(jsonPath("$.data.balance").value(10));
		assertThat(attendanceCount(other)).isZero();
		assertAttendance(other, 10, 10);
		assertAttendance(owner, 0, 10);
		assertThat(coins.findFirstByUserIdOrderByIdDesc(owner).orElseThrow().getGrantDate()).isEqualTo(TODAY);
	}

	@Test
	void concurrentRequestsGrantExactlyOnce() throws Exception {
		long userId = createUser();
		List<Callable<Integer>> requests = new ArrayList<>();
		for (int index = 0; index < 8; index++) {
			requests.add(() -> requestGrant(userId));
		}

		assertThat(runConcurrently(requests)).containsExactlyInAnyOrder(10, 0, 0, 0, 0, 0, 0, 0);
		assertThat(attendanceCount(userId)).isEqualTo(1);
		assertThat(coins.findFirstByUserIdOrderByIdDesc(userId).orElseThrow().getBalanceAfter()).isEqualTo(10);
	}

	@Test
	void concurrentOtherRewardUsingSameUserLockPreservesBothChanges() throws Exception {
		long userId = createUser();
		runConcurrently(List.of(
				() -> requestGrant(userId),
				() -> {
					new TransactionTemplate(transactionManager).executeWithoutResult(status -> {
						users.findActiveByIdForUpdate(userId).orElseThrow();
						int balance = coins.findFirstByUserIdOrderByIdDesc(userId).map(FinCoin::getBalanceAfter).orElse(0);
						insertCoin(userId, 50, balance + 50, "CONFIRM_ALL", TODAY);
					});
					return 0;
				}
		));

		assertThat(attendanceCount(userId)).isEqualTo(1);
		assertThat(coins.findFirstByUserIdOrderByIdDesc(userId).orElseThrow().getBalanceAfter()).isEqualTo(60);
		assertAttendance(userId, 0, 60);
	}

	@Test
	void rollsBackInsertedLedgerWhenTransactionFailsBeforeCommit() throws Exception {
		long userId = createUser();
		assertThatThrownBy(() -> new TransactionTemplate(transactionManager).executeWithoutResult(status -> {
			finCoinService.checkAttendance(userId);
			coins.flush();
			throw new IllegalStateException("failure before commit");
		})).isInstanceOf(IllegalStateException.class).hasMessage("failure before commit");

		assertThat(attendanceCount(userId)).isZero();
		assertThat(coins.findFirstByUserIdOrderByIdDesc(userId)).isEmpty();
		assertAttendance(userId, 10, 10);
	}

	@Test
	void balanceOverflowReturnsServerErrorWithoutGranting() throws Exception {
		long userId = createUser();
		insertCoin(userId, Integer.MAX_VALUE, Integer.MAX_VALUE, "MONTHLY", TODAY);

		mockMvc.perform(authenticated(post(PATH), userId))
				.andExpect(status().isInternalServerError())
				.andExpect(jsonPath("$.success").value(false))
				.andExpect(jsonPath("$.code").value("COMMON_006"));
		assertThat(attendanceCount(userId)).isZero();
		assertThat(coins.findFirstByUserIdOrderByIdDesc(userId).orElseThrow().getBalanceAfter()).isEqualTo(Integer.MAX_VALUE);
	}

	@Test
	void rejectsMissingAndDeletedUsers() throws Exception {
		long deleted = createUser();
		long missing = createUser();
		jdbc.sql("UPDATE users SET deleted_at = CURRENT_TIMESTAMP WHERE id = :id").param("id", deleted).update();
		users.deleteById(missing);

		for (long userId : List.of(deleted, missing)) {
			mockMvc.perform(authenticated(post(PATH), userId))
					.andExpect(status().isNotFound())
					.andExpect(jsonPath("$.code").value("USER_001"));
			assertThat(attendanceCount(userId)).isZero();
		}
	}

	@Test
	void rejectsMissingMalformedExpiredAndRefreshTokens() throws Exception {
		long userId = createUser();
		Clock expiredClock = Clock.fixed(NOW.minus(jwtProperties.accessTokenExpiration()).minusSeconds(60), ZoneOffset.UTC);
		String expiredToken = new JwtTokenProvider(jwtProperties, expiredClock).generateAccessToken(userId);

		mockMvc.perform(post(PATH)).andExpect(status().isUnauthorized()).andExpect(jsonPath("$.code").value("AUTH_005"));
		mockMvc.perform(post(PATH).header("Authorization", "Bearer not-a-jwt"))
				.andExpect(status().isUnauthorized()).andExpect(jsonPath("$.code").value("AUTH_002"));
		mockMvc.perform(post(PATH).header("Authorization", "Bearer " + expiredToken))
				.andExpect(status().isUnauthorized()).andExpect(jsonPath("$.code").value("AUTH_003"));
		mockMvc.perform(post(PATH).header("Authorization", "Bearer " + tokens.generateRefreshToken(userId)))
				.andExpect(status().isUnauthorized()).andExpect(jsonPath("$.code").value("AUTH_002"));
		assertThat(attendanceCount(userId)).isZero();
	}

	@Test
	void oldAttendancePathReturnsNotFoundWithoutGranting() throws Exception {
		long userId = createUser();
		mockMvc.perform(authenticated(post("/api/v1/attendance"), userId))
				.andExpect(status().isNotFound());
		assertThat(attendanceCount(userId)).isZero();
	}

	@Test
	void documentsBodylessPostWithBearerAuthAndBothSuccessExamples() throws Exception {
		String operation = "$.paths['/api/v1/fin-coins/attendance'].post";
		mockMvc.perform(get("/v3/api-docs"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.paths['/api/v1/attendance']").doesNotExist())
				.andExpect(jsonPath(operation + ".tags").value(containsInAnyOrder("코인")))
				.andExpect(jsonPath(operation + ".summary").value("출석 보상 지급"))
				.andExpect(jsonPath(operation + ".security[0].bearerAuth").exists())
				.andExpect(jsonPath(operation + ".parameters").doesNotExist())
				.andExpect(jsonPath(operation + ".requestBody").doesNotExist())
				.andExpect(jsonPath(operation + ".responses['200'].content['application/json'].schema['$ref']")
						.value("#/components/schemas/BaseResponseAttendanceCheckResponse"))
				.andExpect(jsonPath(operation + ".responses['200'].content['application/json'].examples['첫 출석'].value.data.granted").value(10))
				.andExpect(jsonPath(operation + ".responses['200'].content['application/json'].examples['당일 재요청'].value.data.granted").value(0))
				.andExpect(jsonPath(operation + ".responses['401']").exists())
				.andExpect(jsonPath(operation + ".responses['404']").exists())
				.andExpect(jsonPath(operation + ".responses['500']").exists())
				.andExpect(jsonPath("$.components.schemas.AttendanceCheckResponse.properties").value(aMapWithSize(2)))
				.andExpect(jsonPath("$.components.schemas.AttendanceCheckResponse.required").value(containsInAnyOrder("granted", "balance")))
				.andExpect(jsonPath("$.components.schemas.AttendanceCheckResponse.properties.granted.format").value("int32"))
				.andExpect(jsonPath("$.components.schemas.AttendanceCheckResponse.properties.balance.format").value("int32"));
	}

	private long createUser() {
		long id = users.save(User.create("attendance-" + UUID.randomUUID() + "@test.io", "encoded", "출석테스터")).getId();
		testUsers.add(id);
		return id;
	}

	private void insertCoin(long userId, int delta, int balance, String reason, LocalDate date) {
		jdbc.sql("""
				INSERT INTO fin_coin (user_id, delta, balance_after, reason_code, grant_date)
				VALUES (:userId, :delta, :balance, :reason, :date)
				""").param("userId", userId).param("delta", delta).param("balance", balance)
				.param("reason", reason).param("date", date).update();
	}

	private long attendanceCount(long userId) {
		return jdbc.sql("SELECT COUNT(*) FROM fin_coin WHERE user_id = :id AND reason_code = 'ATTEND'")
				.param("id", userId).query(Long.class).single();
	}

	private MockHttpServletRequestBuilder authenticated(MockHttpServletRequestBuilder request, long userId) {
		return request.header("Authorization", "Bearer " + tokens.generateAccessToken(userId));
	}

	private ResultActions assertAttendance(long userId, int granted, int balance) throws Exception {
		return mockMvc.perform(authenticated(post(PATH), userId))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.success").value(true))
				.andExpect(jsonPath("$.code").value("SUCCESS"))
				.andExpect(jsonPath("$.data").value(aMapWithSize(2)))
				.andExpect(jsonPath("$.data.granted").value(granted))
				.andExpect(jsonPath("$.data.balance").value(balance));
	}

	private int requestGrant(long userId) throws Exception {
		String body = mockMvc.perform(authenticated(post(PATH), userId)).andExpect(status().isOk())
				.andReturn().getResponse().getContentAsString();
		return JsonPath.read(body, "$.data.granted");
	}

	private List<Integer> runConcurrently(List<Callable<Integer>> jobs) throws Exception {
		ExecutorService executor = Executors.newFixedThreadPool(jobs.size());
		CountDownLatch ready = new CountDownLatch(jobs.size());
		CountDownLatch start = new CountDownLatch(1);
		try {
			List<Future<Integer>> futures = new ArrayList<>();
			for (Callable<Integer> job : jobs) {
				futures.add(executor.submit(() -> {
					ready.countDown();
					if (!start.await(10, TimeUnit.SECONDS)) throw new IllegalStateException("start timed out");
					return job.call();
				}));
			}
			assertThat(ready.await(10, TimeUnit.SECONDS)).isTrue();
			start.countDown();
			List<Integer> results = new ArrayList<>();
			for (Future<Integer> future : futures) results.add(future.get(30, TimeUnit.SECONDS));
			return results;
		} finally {
			start.countDown();
			executor.shutdownNow();
			assertThat(executor.awaitTermination(10, TimeUnit.SECONDS)).isTrue();
		}
	}


}
