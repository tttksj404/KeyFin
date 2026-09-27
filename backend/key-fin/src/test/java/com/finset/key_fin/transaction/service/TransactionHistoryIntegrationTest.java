package com.finset.key_fin.transaction.service;

import com.finset.key_fin.support.SpringIntegrationTestSupport;
import com.finset.key_fin.transaction.dto.request.TransactionClassificationRequest;
import com.finset.key_fin.transaction.dto.response.TransactionClassificationResponse;
import com.finset.key_fin.transaction.dto.response.TransactionListResponse;
import com.finset.key_fin.transaction.entity.ExcludeTag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;

@Transactional
@Sql("/sql/transaction-history-fixture.sql")
class TransactionHistoryIntegrationTest extends SpringIntegrationTestSupport {

	private static final long USER_ID = 987L;

	@Autowired
	private TransactionService transactionService;

	@Test
	void 현재_사용자의_취소와_제외_거래를_포함해_최신순으로_조회한다() {
		TransactionListResponse response = transactionService.getTransactions(
				USER_ID, "202609", null, null, null, null, null, 20);

		assertThat(response.items()).extracting("id").containsExactly(8190L, 8203L, 8202L, 8201L);
		assertThat(response.items()).extracting("status")
				.extracting(Object::toString)
				.containsExactly("NORMAL", "CANCELED", "NORMAL", "NORMAL");
		assertThat(response.items().get(2).excludeTag().name()).isEqualTo("DUTCH");
		assertThat(response.items().get(2).adjustedAmount()).isEqualTo(15_000L);
		assertThat(response.nextCursor()).isNull();
	}

	@Test
	void 봉투와_세분류_필터를_적용한다() {
		TransactionListResponse response = transactionService.getTransactions(
				USER_ID, "202609", 1, 102, null, null, null, 20);

		assertThat(response.items()).hasSize(1);
		assertThat(response.items().getFirst())
				.extracting("id", "envelopeId", "subcategoryId", "subcategoryName")
				.containsExactly(8201L, 1, 102, "카페");
	}

	@Test
	void cursor_다음_페이지가_중복_없이_이어진다() {
		TransactionListResponse first = transactionService.getTransactions(
				USER_ID, "202609", null, null, null, null, null, 2);
		TransactionListResponse second = transactionService.getTransactions(
				USER_ID, "202609", null, null, null, null, first.nextCursor(), 2);

		assertThat(first.items()).extracting("id").containsExactly(8190L, 8203L);
		assertThat(first.nextCursor()).isEqualTo(8203L);
		assertThat(second.items()).extracting("id").containsExactly(8202L, 8201L);
		assertThat(second.nextCursor()).isNull();
	}

	@Test
	@Sql({"/sql/transaction-history-fixture.sql", "/sql/transaction-pending-fixture.sql"})
	void 미확정_정상_출금_거래만_조회한다() {
		TransactionListResponse response = transactionService.getPendingTransactions(USER_ID, null, 20);

		assertThat(response.items()).extracting("id").containsExactly(8210L);
		assertThat(response.items().getFirst().confirmStatus().name()).isEqualTo("PENDING");
		assertThat(response.items().getFirst().status().name()).isEqualTo("NORMAL");
		assertThat(response.items().getFirst().txType().name()).isEqualTo("CARD");
	}

	@Test
	@Sql({"/sql/transaction-history-fixture.sql", "/sql/transaction-pending-fixture.sql"})
	void 미확정_거래를_세분류로_확정하면_목록에서_제외된다() {
		TransactionClassificationResponse classified = transactionService.classifyTransaction(
				USER_ID, 8210L, new TransactionClassificationRequest(102, null, null)
		);

		assertThat(classified.subcategoryId()).isEqualTo(102);
		assertThat(classified.excludeTag()).isEqualTo(ExcludeTag.NONE);
		assertThat(classified.confirmStatus().name()).isEqualTo("CONFIRMED");
		assertThat(transactionService.getPendingTransactions(USER_ID, null, 20).items()).isEmpty();
	}

	@Test
	@Sql({"/sql/transaction-history-fixture.sql", "/sql/transaction-pending-fixture.sql"})
	void 환급_입금을_세분류와_RESTORE로_확정한다() {
		TransactionClassificationResponse classified = transactionService.classifyTransaction(
				USER_ID, 8211L, new TransactionClassificationRequest(301, ExcludeTag.RESTORE, null)
		);

		assertThat(classified.subcategoryId()).isEqualTo(301);
		assertThat(classified.excludeTag()).isEqualTo(ExcludeTag.RESTORE);
		assertThat(classified.confirmStatus().name()).isEqualTo("CONFIRMED");
	}
}
