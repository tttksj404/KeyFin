package com.finset.key_fin.payment.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlConfig;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.payment.client.FinanceTransferClient;
import com.finset.key_fin.payment.dto.response.FinanceTransferResult;
import com.finset.key_fin.payment.entity.AuditLog;
import com.finset.key_fin.payment.entity.AuditLog.AuditAction;
import com.finset.key_fin.payment.entity.TransferStatus;
import com.finset.key_fin.payment.exception.PaymentErrorCode;
import com.finset.key_fin.payment.repository.AuditLogRepository;
import com.finset.key_fin.payment.repository.PrepareTransferRepository;
import com.finset.key_fin.support.SpringIntegrationTestSupport;

@Sql(scripts = "/sql/transfer-approve-fixture.sql", config = @SqlConfig(encoding = "UTF-8"))
@Sql(scripts = "/sql/transfer-approve-cleanup.sql", executionPhase = Sql.ExecutionPhase.AFTER_TEST_METHOD)
class TransferApproveConcurrencyTest extends SpringIntegrationTestSupport {

	private static final long USER = 986L;
	private static final long TRANSFER = 9901L;

	@Autowired
	private TransferService transferService;
	@Autowired
	private PrepareTransferRepository prepareTransferRepository;
	@Autowired
	private AuditLogRepository auditLogRepository;

	@Test
	@DisplayName("같은 제안을 동시에 두 번 승인하면 이체는 1회, 하나는 EXECUTED·하나는 409, 감사는 EXECUTE 1건")
	void concurrentApprovalsExecuteOnce() throws Exception {
		when(financeTransferClient.transfer(any(), any(), any(), any(), anyLong(), any())).thenAnswer(invocation -> {
			Thread.sleep(300);
			return FinanceTransferResult.EXECUTED;
		});
		CountDownLatch start = new CountDownLatch(1);
		Callable<Object> attempt = () -> {
			start.await(5, TimeUnit.SECONDS);
			try {
				return transferService.approve(USER, TRANSFER).status();
			} catch (BusinessException e) {
				return e.getErrorCode();
			}
		};
		ExecutorService pool = Executors.newFixedThreadPool(2);
		try {
			List<Future<Object>> futures = List.of(pool.submit(attempt), pool.submit(attempt));
			start.countDown();
			List<Object> outcomes = new ArrayList<>();
			for (Future<Object> future : futures) {
				outcomes.add(future.get(20, TimeUnit.SECONDS));
			}
			assertThat(outcomes).containsExactlyInAnyOrder(TransferStatus.EXECUTED, PaymentErrorCode.TRANSFER_NOT_PROPOSED);
		} finally {
			pool.shutdownNow();
		}

		verify(financeTransferClient, times(1)).transfer(any(), any(), any(), any(), anyLong(), any());
		assertThat(prepareTransferRepository.findById(TRANSFER).orElseThrow().getStatus()).isEqualTo(TransferStatus.EXECUTED);
		List<AuditLog> logs = auditLogRepository.findAllByTargetTypeAndTargetIdOrderByIdAsc(
				AuditLog.TARGET_PREPARE_TRANSFER, String.valueOf(TRANSFER));
		assertThat(logs).extracting(AuditLog::getAction).containsExactly(AuditAction.EXECUTE);
	}
}
