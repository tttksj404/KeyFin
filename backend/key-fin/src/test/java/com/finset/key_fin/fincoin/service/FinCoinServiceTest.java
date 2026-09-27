package com.finset.key_fin.fincoin.service;

import com.finset.key_fin.fincoin.dto.response.FinCoinResponse;
import com.finset.key_fin.fincoin.dto.response.FinCoinResponse.FinCoinHistoryResponse;
import com.finset.key_fin.fincoin.entity.FinCoinReason;
import com.finset.key_fin.fincoin.entity.FinCoin;
import com.finset.key_fin.fincoin.repository.FinCoinRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.support.SpringIntegrationTestSupport;
import com.finset.key_fin.user.exception.UserErrorCode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.EnumSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.data.domain.Limit;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.transaction.annotation.Transactional;

import java.sql.SQLException;
import java.time.LocalDate;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.tuple;

@Transactional
@Sql("/sql/fin-coin-history-fixture.sql")
class FinCoinServiceTest extends SpringIntegrationTestSupport {

	private static final long USER = 981L;

	@Autowired
	private FinCoinService finCoinService;

	@Autowired
	private FinCoinRepository finCoinRepository;

	@Autowired
	private JdbcClient jdbcClient;

	@ParameterizedTest
	@EnumSource(value = FinCoinReason.class, names = {"ATTEND", "CONFIRM_ALL", "WEEKLY", "MONTHLY"})
	void databaseRejectsDuplicateRewardsButAllowsNextDate(FinCoinReason reason) {
		LocalDate date = LocalDate.of(2026, 9, 17);
		String insert = """
				INSERT INTO fin_coin (user_id, delta, balance_after, reason_code, grant_date)
				VALUES (:userId, 10, :balance, :reason, :date)
				""";
		jdbcClient.sql(insert).param("userId", USER).param("balance", 710)
				.param("reason", reason.name()).param("date", date).update();

		assertThatThrownBy(() -> jdbcClient.sql(insert).param("userId", USER).param("balance", 720)
				.param("reason", reason.name()).param("date", date).update())
				.isInstanceOf(DuplicateKeyException.class)
				.rootCause().isInstanceOfSatisfying(SQLException.class, exception -> {
					assertThat(exception.getErrorCode()).isEqualTo(1062);
					assertThat(exception.getMessage()).contains("uq_coin_grant");
				});

		jdbcClient.sql(insert).param("userId", USER).param("balance", 720)
				.param("reason", reason.name()).param("date", date.plusDays(1)).update();
		assertThat(jdbcClient.sql("""
				SELECT reward_grant_date FROM fin_coin
				WHERE user_id = :userId AND reason_code = :reason AND grant_date >= :date
				ORDER BY grant_date
				""").param("userId", USER).param("reason", reason.name()).param("date", date)
				.query(LocalDate.class).list()).containsExactly(date, date.plusDays(1));
	}

	@Test
	void databaseAllowsDifferentRewardReasonsForSameUserAndDate() {
		LocalDate date = LocalDate.of(2026, 9, 17);
		jdbcClient.sql("""
				INSERT INTO fin_coin (user_id, delta, balance_after, reason_code, grant_date) VALUES
				(:userId, 10, 710, 'ATTEND', :date),
				(:userId, 10, 720, 'CONFIRM_ALL', :date),
				(:userId, 10, 730, 'WEEKLY', :date),
				(:userId, 10, 740, 'MONTHLY', :date)
				""").param("userId", USER).param("date", date).update();

		assertThat(jdbcClient.sql("""
				SELECT reason_code FROM fin_coin WHERE user_id = :userId AND grant_date = :date
				""").param("userId", USER).param("date", date).query(String.class).list())
				.containsExactlyInAnyOrder("ATTEND", "CONFIRM_ALL", "WEEKLY", "MONTHLY");
	}

	@Test
	void purchasesAllowMultipleEntriesPerDayWithNullRewardGrantDate() {
		LocalDate date = LocalDate.of(2026, 9, 17);
		jdbcClient.sql("""
				INSERT INTO fin_coin (user_id, delta, balance_after, reason_code, grant_date) VALUES
				(:userId, -20, 680, 'PURCHASE', :date),
				(:userId, -30, 650, 'PURCHASE', :date),
				(:userId, 0, 650, 'PURCHASE', :date)
				""").param("userId", USER).param("date", date).update();

		assertThat(jdbcClient.sql("""
				SELECT reward_grant_date FROM fin_coin
				WHERE user_id = :userId AND reason_code = 'PURCHASE' AND grant_date = :date
				""").param("userId", USER).param("date", date).query(LocalDate.class).list())
				.hasSize(3).containsOnlyNulls();
	}

	@Test
	void hasUserAndIdIndexForLedgerQueries() {
		assertThat(jdbcClient.sql("""
				SELECT column_name FROM information_schema.statistics
				WHERE table_schema = DATABASE() AND table_name = 'fin_coin'
				  AND index_name = 'idx_fin_coin_user_id'
				ORDER BY seq_in_index
				""").query(String.class).list()).containsExactly("user_id", "id");
	}

	@Test
	void limitsDatabaseResultsBeforeResponseTrimming() {
		assertThat(finCoinRepository.findByUserIdOrderByIdDesc(USER, Limit.of(2)))
				.extracting(FinCoin::getId)
				.containsExactly(8_100_000_009L, 8_100_000_007L);
		assertThat(finCoinRepository.findByUserIdAndIdLessThanOrderByIdDesc(
				USER, 8_100_000_007L, Limit.of(2)))
				.extracting(FinCoin::getId)
				.containsExactly(8_100_000_005L, 8_100_000_003L);
	}

	@ParameterizedTest
	@CsvSource({"981, 700", "982, 2000"})
	void returnsLatestBalanceByUserAndIdAfterPurchase(long userId, int expectedBalance) {
		assertThat(finCoinService.getFinCoinBalance(userId).balance()).isEqualTo(expectedBalance);
	}

	@Test
	void returnsZeroBalanceForUserWithoutHistory() {
		assertThat(finCoinService.getFinCoinBalance(983L).balance()).isZero();
	}

	@Test
	void returnsZeroBalanceAfterSpendingAllCoins() {
		jdbcClient.sql("""
				INSERT INTO fin_coin (id, user_id, delta, balance_after, reason_code, grant_date)
				VALUES (8100000011, 981, -700, 0, 'PURCHASE', '2026-09-11')
				""").update();

		assertThat(finCoinService.getFinCoinBalance(USER).balance()).isZero();
	}

	@ParameterizedTest
	@ValueSource(longs = {984, 985})
	void rejectsBalanceRequestForDeletedOrMissingUser(long userId) {
		assertThatThrownBy(() -> finCoinService.getFinCoinBalance(userId))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode()).isEqualTo(UserErrorCode.USER_NOT_FOUND));
	}

	@Test
	void pagesByDescendingId() {
		FinCoinResponse first = finCoinService.getFinCoins(USER, null, 2);
		assertThat(first.items()).extracting(FinCoinHistoryResponse::id)
				.containsExactly(8_100_000_009L, 8_100_000_007L);
		assertThat(first.nextCursor()).isEqualTo(8_100_000_007L);

		FinCoinResponse middle = finCoinService.getFinCoins(USER, first.nextCursor(), 2);
		assertThat(middle.items()).extracting(FinCoinHistoryResponse::id)
				.containsExactly(8_100_000_005L, 8_100_000_003L);
		assertThat(middle.nextCursor()).isEqualTo(8_100_000_003L);

		FinCoinResponse last = finCoinService.getFinCoins(USER, middle.nextCursor(), 2);
		assertThat(last.items()).extracting(FinCoinHistoryResponse::id).containsExactly(8_100_000_001L);
		assertThat(last.nextCursor()).isNull();
	}

	@Test
	void returnsNullCursorWhenExactlySizeRowsRemain() {
		FinCoinResponse first = finCoinService.getFinCoins(USER, null, 5);
		assertThat(first.items()).hasSize(5);
		assertThat(first.nextCursor()).isNull();

		FinCoinResponse last = finCoinService.getFinCoins(USER, 8_100_000_005L, 2);
		assertThat(last.items()).extracting(FinCoinHistoryResponse::id)
				.containsExactly(8_100_000_003L, 8_100_000_001L);
		assertThat(last.nextCursor()).isNull();
	}

	@Test
	void returnsOneItemAndItsIdAsCursorForSizeOne() {
		FinCoinResponse result = finCoinService.getFinCoins(USER, null, 1);
		assertThat(result.items()).extracting(FinCoinHistoryResponse::id).containsExactly(8_100_000_009L);
		assertThat(result.nextCursor()).isEqualTo(8_100_000_009L);
	}

	@Test
	void mapsAllReasonTextsAndPreservesLedgerValues() {
		FinCoinResponse result = finCoinService.getFinCoins(USER, null, 100);
		assertThat(result.items()).extracting(
				FinCoinHistoryResponse::reasonCode, FinCoinHistoryResponse::reasonText,
				FinCoinHistoryResponse::delta, FinCoinHistoryResponse::balanceAfter, FinCoinHistoryResponse::grantDate
		).containsExactly(
				tuple(FinCoinReason.PURCHASE, "아이템 구매", -150, 700, LocalDate.of(2026, 9, 2)),
				tuple(FinCoinReason.MONTHLY, "월간 보상", 500, 850, LocalDate.of(2026, 9, 4)),
				tuple(FinCoinReason.WEEKLY, "주간 보상", 200, 350, LocalDate.of(2026, 9, 3)),
				tuple(FinCoinReason.CONFIRM_ALL, "거래 내역 전체 확인 보상", 50, 150, LocalDate.of(2026, 9, 10)),
				tuple(FinCoinReason.ATTEND, "출석 보상", 100, 100, LocalDate.of(2026, 9, 5))
		);
		assertThat(result.nextCursor()).isNull();
	}

	@Test
	void isolatesOtherUsersHistory() {
		FinCoinResponse result = finCoinService.getFinCoins(982L, null, 20);
		assertThat(result.items()).extracting(FinCoinHistoryResponse::id)
				.containsExactly(8_100_000_010L, 8_100_000_006L);
		assertThat(result.nextCursor()).isNull();
	}

	@Test
	void returnsEmptyItemsForNewUser() {
		FinCoinResponse result = finCoinService.getFinCoins(983L, null, 20);
		assertThat(result.items()).isEmpty();
		assertThat(result.nextCursor()).isNull();
	}

	@ParameterizedTest
	@ValueSource(longs = {1, 8_100_000_001L})
	void returnsEmptyItemsWhenCursorIsPastAllItems(long cursor) {
		FinCoinResponse result = finCoinService.getFinCoins(USER, cursor, 20);
		assertThat(result.items()).isEmpty();
		assertThat(result.nextCursor()).isNull();
	}

	@Test
	void usesNonexistentCursorAsExclusiveBoundary() {
		FinCoinResponse result = finCoinService.getFinCoins(USER, 8_100_000_004L, 20);
		assertThat(result.items()).extracting(FinCoinHistoryResponse::id)
				.containsExactly(8_100_000_003L, 8_100_000_001L);
		assertThat(result.nextCursor()).isNull();
	}

	@Test
	void usesOtherUsersCursorAsBoundaryWithoutExposingTheirItems() {
		FinCoinResponse result = finCoinService.getFinCoins(USER, 8_100_000_006L, 2);
		assertThat(result.items()).extracting(FinCoinHistoryResponse::id)
				.containsExactly(8_100_000_005L, 8_100_000_003L);
		assertThat(result.nextCursor()).isEqualTo(8_100_000_003L);
	}

	@Test
	void acceptsCursorAboveLatestHistoryId() {
		FinCoinResponse result = finCoinService.getFinCoins(USER, Long.MAX_VALUE, 2);
		assertThat(result.items()).extracting(FinCoinHistoryResponse::id)
				.containsExactly(8_100_000_009L, 8_100_000_007L);
		assertThat(result.nextCursor()).isEqualTo(8_100_000_007L);
	}

	@Test
	void newHistoryBetweenPagesDoesNotRepeatItems() {
		FinCoinResponse first = finCoinService.getFinCoins(USER, null, 2);
		jdbcClient.sql("""
				INSERT INTO fin_coin (id, user_id, delta, balance_after, reason_code, grant_date)
				VALUES (8100000011, 981, 20, 720, 'ATTEND', '2026-09-11')
				""").update();

		FinCoinResponse next = finCoinService.getFinCoins(USER, first.nextCursor(), 2);
		assertThat(next.items()).extracting(FinCoinHistoryResponse::id)
				.containsExactly(8_100_000_005L, 8_100_000_003L);
		assertThat(next.nextCursor()).isEqualTo(8_100_000_003L);
	}

	@ParameterizedTest
	@ValueSource(longs = {984, 985})
	void rejectsDeletedOrMissingUser(long userId) {
		assertThatThrownBy(() -> finCoinService.getFinCoins(userId, null, 20))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode()).isEqualTo(UserErrorCode.USER_NOT_FOUND));
	}
}
