package com.finset.key_fin.payment.service;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Import;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlConfig;
import org.springframework.transaction.annotation.Transactional;
import com.finset.key_fin.support.SpringIntegrationTestSupport;

@Transactional
@Sql(scripts = "/sql/transfer-proposal-fixture.sql", config = @SqlConfig(encoding = "UTF-8"))
class ShortageWarningServiceTest extends SpringIntegrationTestSupport {

	private static final long USER = 986L;
	private static final long LIVING = 9504L;
	private static final long RENT = 9505L;

	@Autowired
	private ShortageWarningService shortageWarningService;
	@Autowired
	private JdbcTemplate jdbcTemplate;
	@Autowired
	private StringRedisTemplate redisTemplate;

	@BeforeEach
	void clearCooldown() {
		Set<String> keys = redisTemplate.keys("notification:payment:shortage:*");
		if (keys != null && !keys.isEmpty()) {
			redisTemplate.delete(keys);
		}
	}

	@Test
	@DisplayName("실행된 제안이 있는 출금 건이 다시 부족해지면 WARNING 한 건 — 본문은 계좌의 오늘·내일 부족액 합, 같은 날 재평가에는 나가지 않는다")
	void warnsOnceADayAfterExecutedTransfer() {
		markExecuted(9901L);

		shortageWarningService.evaluate(USER, LIVING);
		shortageWarningService.evaluate(USER, LIVING);

		List<Map<String, Object>> rows = notifications();
		assertThat(rows).hasSize(1);
		assertThat(rows.get(0))
				.containsEntry("noti_type", "WARNING")
				.containsEntry("title", ShortageWarningService.TITLE)
				.containsEntry("body", "생활비 계좌에 130,000원이 더 필요해요")
				.containsEntry("ref_id", "9504")
				.containsEntry("requires_action", true);
	}

	@Test
	@DisplayName("제안이 PROPOSED로만 남았거나 이력이 없으면 알리지 않는다(배치가 처리)")
	void staysSilentWithoutExecutedTransfer() {
		shortageWarningService.evaluate(USER, LIVING);

		assertThat(notifications()).isEmpty();
	}

	@Test
	@DisplayName("실행된 제안이 있어도 잔액이 충분하면 알리지 않는다")
	void staysSilentWhenBalanceCoversWithdrawals() {
		markExecuted(9901L);
		jdbcTemplate.update("UPDATE accounts SET balance = 700000 WHERE id = ?", LIVING);
		markExecuted(9902L);

		shortageWarningService.evaluate(USER, LIVING);
		shortageWarningService.evaluate(USER, RENT);

		assertThat(notifications()).isEmpty();
	}

	@Test
	@DisplayName("실행된 제안이 오늘·내일 창 밖의 다른 출금 건(9904 월세 8/14)뿐이면 알리지 않는다")
	void staysSilentWhenExecutedTransferIsForAnotherWithdrawal() {
		jdbcTemplate.update("UPDATE prepare_transfers SET status = 'CANCELED', fail_reason = '출금일 경과' WHERE id = 9901");

		shortageWarningService.evaluate(USER, LIVING);

		assertThat(notifications()).isEmpty();
	}

	private void markExecuted(long id) {
		jdbcTemplate.update("UPDATE prepare_transfers SET status = 'EXECUTED', institution_tx_no = CONCAT('2026091008300000', id), "
				+ "executed_at = '2026-09-10 08:31:00' WHERE id = ?", id);
	}

	private List<Map<String, Object>> notifications() {
		return jdbcTemplate.queryForList(
				"SELECT noti_type, title, body, ref_id, requires_action FROM notifications WHERE user_id = ? ORDER BY id", USER);
	}
}
