package com.finset.key_fin.payment.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.LocalDate;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.event.ApplicationEvents;
import org.springframework.test.context.event.RecordApplicationEvents;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlConfig;
import org.springframework.transaction.annotation.Transactional;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.exception.CommonErrorCode;
import com.finset.key_fin.payment.client.FinanceTransferClient;
import com.finset.key_fin.payment.dto.response.FinanceTransferResult;
import com.finset.key_fin.payment.dto.response.FinanceTransferResult.Status;
import com.finset.key_fin.payment.dto.response.PaymentCalendarResponse.CalendarItemType;
import com.finset.key_fin.payment.dto.response.TransferApproveResponse;
import com.finset.key_fin.payment.dto.response.TransferDetailResponse;
import com.finset.key_fin.payment.dto.response.TransferListResponse;
import com.finset.key_fin.payment.dto.response.TransferResponse;
import com.finset.key_fin.payment.entity.AuditLog;
import com.finset.key_fin.payment.entity.AuditLog.AuditAction;
import com.finset.key_fin.payment.entity.PrepareTransfer;
import com.finset.key_fin.payment.entity.TransferStatus;
import com.finset.key_fin.payment.event.TransferCompleted;
import com.finset.key_fin.payment.exception.PaymentErrorCode;
import com.finset.key_fin.payment.repository.AuditLogRepository;
import com.finset.key_fin.payment.repository.PrepareTransferRepository;
import com.finset.key_fin.support.SpringIntegrationTestSupport;

@Transactional
@RecordApplicationEvents
@Sql(scripts = "/sql/transfer-approve-fixture.sql", config = @SqlConfig(encoding = "UTF-8"))
class TransferServiceTest extends SpringIntegrationTestSupport {

	private static final long USER = 986L;
	private static final String USER_KEY = "test-user-key-986";
	private static final String INCOME_NO = "0019860000000006";
	private static final String LIVING_NO = "0019860000000001";

	@Autowired
	private TransferService transferService;
	@Autowired
	private PrepareTransferRepository prepareTransferRepository;
	@Autowired
	private AuditLogRepository auditLogRepository;
	@Autowired
	private TransferWriter transferWriter;
	@Autowired
	private ApplicationEvents events;

	@Test
	@DisplayName("승인: 4검사 통과 → 번호 채번·APPROVED → 금융망 이체(수입→출금 계좌) → EXECUTED + EXECUTE 감사")
	void approvesAndExecutes() {
		when(financeTransferClient.transfer(eq(USER_KEY), anyString(), eq(INCOME_NO), eq(LIVING_NO), eq(230000L), eq("KeyFin 결제 준비 - 월세")))
				.thenReturn(FinanceTransferResult.EXECUTED);

		TransferApproveResponse response = transferService.approve(USER, 9901L);

		assertThat(response.status()).isEqualTo(TransferStatus.EXECUTED);
		assertThat(response.executedAt()).isNotNull();
		PrepareTransfer transfer = prepareTransferRepository.findById(9901L).orElseThrow();
		assertThat(transfer.getStatus()).isEqualTo(TransferStatus.EXECUTED);
		assertThat(transfer.getInstitutionTxNo()).hasSize(20);
		assertThat(auditOf(9901L)).extracting(AuditLog::getAction).containsExactly(AuditAction.EXECUTE);
	}

	@Test
	@DisplayName("동의 OFF → 403 PAY_007, 이체 호출 없음, HOLD 감사, 상태는 PROPOSED 유지")
	void holdsWhenConsentOff() {
		assertThatThrownBy(() -> transferService.approve(987L, 9907L))
				.isInstanceOf(BusinessException.class)
				.extracting(e -> ((BusinessException) e).getErrorCode())
				.isEqualTo(PaymentErrorCode.TRANSFER_CONSENT_OFF);

		verify(financeTransferClient, never()).transfer(any(), any(), any(), any(), anyLong(), any());
		assertThat(prepareTransferRepository.findById(9907L).orElseThrow().isProposed()).isTrue();
		assertThat(auditOf(9907L)).extracting(AuditLog::getAction).containsExactly(AuditAction.HOLD);
	}

	@Test
	@DisplayName("1회 한도 초과 → PAY_008, 1일 한도(오늘 실행 550,000 + 300,000 > 800,000) → PAY_009, 출금 계좌 부적격 → PAY_010")
	void holdsOnLimitsAndAccount() {
		assertThatThrownBy(() -> transferService.approve(USER, 9902L))
				.extracting(e -> ((BusinessException) e).getErrorCode()).isEqualTo(PaymentErrorCode.TRANSFER_LIMIT_ONCE);
		assertThatThrownBy(() -> transferService.approve(USER, 9903L))
				.extracting(e -> ((BusinessException) e).getErrorCode()).isEqualTo(PaymentErrorCode.TRANSFER_LIMIT_DAILY);
		assertThatThrownBy(() -> transferService.approve(988L, 9908L))
				.extracting(e -> ((BusinessException) e).getErrorCode()).isEqualTo(PaymentErrorCode.TRANSFER_ACCOUNT_INELIGIBLE);

		verify(financeTransferClient, never()).transfer(any(), any(), any(), any(), anyLong(), any());
		assertThat(auditOf(9902L)).hasSize(1);
		assertThat(auditOf(9903L)).extracting(AuditLog::getBasis).singleElement().asString().contains("550000");
	}

	@Test
	@DisplayName("금융망 잔액 부족(A1014) → FAILED + FAIL 감사 + 422 PAY_011")
	void failsOnInsufficientBalance() {
		when(financeTransferClient.transfer(any(), any(), any(), any(), anyLong(), any()))
				.thenReturn(new FinanceTransferResult(Status.INSUFFICIENT_BALANCE, "A1014"));

		assertThatThrownBy(() -> transferService.approve(USER, 9901L))
				.extracting(e -> ((BusinessException) e).getErrorCode()).isEqualTo(PaymentErrorCode.TRANSFER_INSUFFICIENT_BALANCE);

		PrepareTransfer transfer = prepareTransferRepository.findById(9901L).orElseThrow();
		assertThat(transfer.getStatus()).isEqualTo(TransferStatus.FAILED);
		assertThat(transfer.getFailReason()).startsWith("A1014");
		assertThat(auditOf(9901L)).extracting(AuditLog::getAction).containsExactly(AuditAction.FAIL);
	}

	@Test
	@DisplayName("APPROVED로 남은 건(응답 유실)은 검사 없이 같은 기관거래고유번호로 재시도, H1007이면 EXECUTED")
	void recoversApprovedWithSameTransactionNo() {
		when(financeTransferClient.transfer(eq(USER_KEY), eq("20260901083000000009"), eq(INCOME_NO), eq(LIVING_NO), eq(120000L), any()))
				.thenReturn(FinanceTransferResult.ALREADY_PROCESSED);

		TransferApproveResponse response = transferService.approve(USER, 9905L);

		assertThat(response.status()).isEqualTo(TransferStatus.EXECUTED);
		assertThat(prepareTransferRepository.findById(9905L).orElseThrow().getInstitutionTxNo()).isEqualTo("20260901083000000009");
		assertThat(auditOf(9905L)).extracting(AuditLog::getBasis).singleElement().asString().contains("H1007");
	}

	@Test
	@DisplayName("실행·실패로 끝난 건은 409, 남의 제안은 404")
	void rejectsWrongStateOrOwner() {
		assertThatThrownBy(() -> transferService.approve(USER, 9909L))
				.extracting(e -> ((BusinessException) e).getErrorCode()).isEqualTo(PaymentErrorCode.TRANSFER_NOT_PROPOSED);
		assertThatThrownBy(() -> transferService.approve(USER, 9907L))
				.extracting(e -> ((BusinessException) e).getErrorCode()).isEqualTo(PaymentErrorCode.TRANSFER_NOT_FOUND);
	}

	@Test
	@DisplayName("보류: 상태는 PROPOSED 그대로, HOLD 감사만 남는다. 실행된 건은 409")
	void postponeLeavesAuditOnly() {
		transferService.postpone(USER, 9901L);

		assertThat(prepareTransferRepository.findById(9901L).orElseThrow().isProposed()).isTrue();
		assertThat(auditOf(9901L)).extracting(AuditLog::getBasis).singleElement().asString().startsWith(TransferService.POSTPONE_BASIS);
		assertThatThrownBy(() -> transferService.postpone(USER, 9904L))
				.extracting(e -> ((BusinessException) e).getErrorCode()).isEqualTo(PaymentErrorCode.TRANSFER_NOT_PROPOSED);
	}

	@Test
	@DisplayName("목록: 상태 필터는 선택, 없으면 전체 최신순. 목적 이름은 고정지출 이름 또는 카드명")
	void listsWithOptionalFilter() {
		List<TransferResponse> proposed = transferService.list(USER, TransferStatus.PROPOSED, null, null, null).items();
		assertThat(proposed).extracting(TransferResponse::id).containsExactly(9903L, 9902L, 9901L);
		assertThat(proposed.get(0).purpose().type()).isEqualTo(CalendarItemType.CARD_BILL);
		assertThat(proposed.get(0).purpose().name()).isEqualTo("신한 테스트카드");
		assertThat(proposed.get(2).purpose().name()).isEqualTo("월세");

		TransferListResponse all = transferService.list(USER, null, null, null, null);
		assertThat(all.items()).hasSize(7);
		assertThat(all.items().get(0).id()).isEqualTo(9909L);
		assertThat(all.nextCursor()).isNull();
	}

	@Test
	@DisplayName("페이징: size+1 읽기로 다음 페이지 유무를 판단하고, 커서(마지막 id)로 이어 가면 중복·누락 없이 전체를 순회한다")
	void pagesWithCursor() {
		TransferListResponse first = transferService.list(USER, null, null, null, 3);
		assertThat(first.items()).extracting(TransferResponse::id).containsExactly(9909L, 9906L, 9905L);
		assertThat(first.nextCursor()).isEqualTo(9905L);

		TransferListResponse second = transferService.list(USER, null, null, first.nextCursor(), 3);
		assertThat(second.items()).extracting(TransferResponse::id).containsExactly(9904L, 9903L, 9902L);
		assertThat(second.nextCursor()).isEqualTo(9902L);

		TransferListResponse last = transferService.list(USER, null, null, second.nextCursor(), 3);
		assertThat(last.items()).extracting(TransferResponse::id).containsExactly(9901L);
		assertThat(last.nextCursor()).isNull();
	}

	@Test
	@DisplayName("필터: month는 대상 출금일 기준이며 status와 함께 적용된다. 다른 사용자 행은 보이지 않고, 잘못된 month·size·cursor는 COMMON_001")
	void filtersAndValidates() {
		assertThat(transferService.list(USER, null, "202609", null, null).items()).hasSize(7);
		assertThat(transferService.list(USER, null, "202610", null, null).items()).isEmpty();
		assertThat(transferService.list(USER, TransferStatus.EXECUTED, "202609", null, null).items())
				.extracting(TransferResponse::id).containsExactly(9906L, 9904L);
		assertThat(transferService.list(987L, null, null, null, null).items())
				.extracting(TransferResponse::id).containsExactly(9907L);

		for (Runnable call : List.<Runnable>of(
				() -> transferService.list(USER, null, "2026-09", null, null),
				() -> transferService.list(USER, null, null, null, 0),
				() -> transferService.list(USER, null, null, null, 101),
				() -> transferService.list(USER, null, null, 0L, null))) {
			assertThatThrownBy(call::run).isInstanceOf(BusinessException.class)
					.extracting(e -> ((BusinessException) e).getErrorCode()).isEqualTo(CommonErrorCode.INVALID_INPUT_VALUE);
		}
	}

	@Test
	@DisplayName("상세: 현재 상태와 감사 타임라인을 오래된 순으로 돌려주고, 남의 제안은 404")
	void detailWithHistory() {
		assertThatThrownBy(() -> transferService.approve(USER, 9902L))
				.isInstanceOf(BusinessException.class);
		transferService.postpone(USER, 9902L);

		TransferDetailResponse detail = transferService.detail(USER, 9902L);

		assertThat(detail.transfer().id()).isEqualTo(9902L);
		assertThat(detail.transfer().status()).isEqualTo(TransferStatus.PROPOSED);
		assertThat(detail.transfer().purpose().name()).isEqualTo("월세");
		assertThat(detail.history()).extracting(TransferDetailResponse.HistoryEntry::action)
				.containsExactly(AuditAction.HOLD, AuditAction.HOLD);
		assertThat(detail.history().get(0).basis()).contains("PAY_008").contains("350000");
		assertThat(detail.history().get(1).basis()).startsWith(TransferService.POSTPONE_BASIS);
		assertThat(detail.history()).allSatisfy(entry -> assertThat(entry.at()).isNotNull());

		assertThat(transferService.detail(USER, 9901L).history()).isEmpty();
		assertThatThrownBy(() -> transferService.detail(USER, 9907L))
				.isInstanceOf(BusinessException.class)
				.extracting(e -> ((BusinessException) e).getErrorCode()).isEqualTo(PaymentErrorCode.TRANSFER_NOT_FOUND);
	}

	@Test
	@DisplayName("이미 종결된 건에 complete가 다시 오면 아무것도 쓰지 않고 현재 상태를 돌려준다(중복 감사 없음)")
	void completeIsIdempotentOnFinalState() {
		TransferApproveResponse response = transferWriter.complete(
				USER, 9904L, FinanceTransferResult.EXECUTED, java.time.LocalDateTime.now(), true);

		assertThat(response.status()).isEqualTo(TransferStatus.EXECUTED);
		assertThat(auditOf(9904L)).isEmpty();
	}

	@Test
	@DisplayName("복구 배치: APPROVED 행만 저장된 번호로 재전송, H1007이면 EXECUTED. PROPOSED 행은 건드리지 않는다")
	void recoverApprovedSettlesWithStoredNo() {
		when(financeTransferClient.transfer(eq(USER_KEY), eq("20260901083000000009"), eq(INCOME_NO), eq(LIVING_NO), eq(120000L), any()))
				.thenReturn(FinanceTransferResult.ALREADY_PROCESSED);

		transferService.recoverApproved();

		PrepareTransfer recovered = prepareTransferRepository.findById(9905L).orElseThrow();
		assertThat(recovered.getStatus()).isEqualTo(TransferStatus.EXECUTED);
		assertThat(recovered.getInstitutionTxNo()).isEqualTo("20260901083000000009");
		assertThat(auditOf(9905L)).extracting(AuditLog::getAction).containsExactly(AuditAction.EXECUTE);
		assertThat(prepareTransferRepository.findById(9901L).orElseThrow().isProposed()).isTrue();
		verify(financeTransferClient, times(1)).transfer(any(), any(), any(), any(), anyLong(), any());
	}

	@Test
	@DisplayName("복구 배치: A1014는 FAILED로 마감, 통신 예외가 난 행은 APPROVED로 남겨 다음 회차에 다시 본다")
	void recoverApprovedIsolatesFailures() {
		PrepareTransfer stuck = PrepareTransfer.proposeForFixedExpense(
				USER, 9704L, LocalDate.of(2026, 9, 9), LocalDate.of(2026, 9, 24), 50000L, 9506L, 9504L);
		stuck.approve("20260910083000000077");
		long stuckId = prepareTransferRepository.save(stuck).getId();
		when(financeTransferClient.transfer(any(), eq("20260901083000000009"), any(), any(), anyLong(), any()))
				.thenReturn(new FinanceTransferResult(Status.INSUFFICIENT_BALANCE, "A1014"));
		when(financeTransferClient.transfer(any(), eq("20260910083000000077"), any(), any(), anyLong(), any()))
				.thenThrow(new IllegalStateException("finance down"));

		transferService.recoverApproved();

		PrepareTransfer failed = prepareTransferRepository.findById(9905L).orElseThrow();
		assertThat(failed.getStatus()).isEqualTo(TransferStatus.FAILED);
		assertThat(failed.getFailReason()).startsWith("A1014");
		assertThat(auditOf(9905L)).extracting(AuditLog::getAction).containsExactly(AuditAction.FAIL);
		PrepareTransfer pending = prepareTransferRepository.findById(stuckId).orElseThrow();
		assertThat(pending.isApproved()).isTrue();
		assertThat(pending.getInstitutionTxNo()).isEqualTo("20260910083000000077");
		assertThat(auditOf(stuckId)).isEmpty();
	}

	@Test
	@DisplayName("알림 이벤트: 사용자 승인으로 EXECUTED·FAILED가 되면 그 상태를 담은 TransferCompleted를 한 번 발행한다")
	void publishesCompletedOnUserApproval() {
		when(financeTransferClient.transfer(eq(USER_KEY), anyString(), eq(INCOME_NO), eq(LIVING_NO), eq(230000L), any()))
				.thenReturn(FinanceTransferResult.EXECUTED);
		when(financeTransferClient.transfer(eq(USER_KEY), eq("20260901083000000009"), eq(INCOME_NO), eq(LIVING_NO), eq(120000L), any()))
				.thenReturn(new FinanceTransferResult(Status.INSUFFICIENT_BALANCE, "A1014"));

		transferService.approve(USER, 9901L);
		assertThatThrownBy(() -> transferService.approve(USER, 9905L)).isInstanceOf(BusinessException.class);

		assertThat(events.stream(TransferCompleted.class)).containsExactly(
				new TransferCompleted(USER, 9901L, TransferStatus.EXECUTED),
				new TransferCompleted(USER, 9905L, TransferStatus.FAILED));
	}

	@Test
	@DisplayName("알림 이벤트: 종결된 건의 재-complete와 복구 배치는 발행하지 않는다")
	void doesNotPublishOnIdempotentCompleteOrRecovery() {
		when(financeTransferClient.transfer(eq(USER_KEY), eq("20260901083000000009"), eq(INCOME_NO), eq(LIVING_NO), eq(120000L), any()))
				.thenReturn(FinanceTransferResult.ALREADY_PROCESSED);

		transferWriter.complete(USER, 9904L, FinanceTransferResult.EXECUTED, java.time.LocalDateTime.now(), true);
		transferService.recoverApproved();

		assertThat(prepareTransferRepository.findById(9905L).orElseThrow().getStatus()).isEqualTo(TransferStatus.EXECUTED);
		assertThat(events.stream(TransferCompleted.class)).isEmpty();
	}

	private List<AuditLog> auditOf(long transferId) {
		return auditLogRepository.findAllByTargetTypeAndTargetIdOrderByIdAsc(AuditLog.TARGET_PREPARE_TRANSFER, String.valueOf(transferId));
	}
}
