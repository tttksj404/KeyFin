package com.finset.key_fin.payment.service;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.LocalDate;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.event.ApplicationEvents;
import org.springframework.test.context.event.RecordApplicationEvents;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlConfig;
import org.springframework.transaction.annotation.Transactional;
import com.finset.key_fin.payment.entity.AuditLog;
import com.finset.key_fin.payment.entity.AuditLog.AuditAction;
import com.finset.key_fin.payment.entity.PrepareTransfer;
import com.finset.key_fin.payment.entity.TransferStatus;
import com.finset.key_fin.payment.event.TransferProposed;
import com.finset.key_fin.payment.repository.AuditLogRepository;
import com.finset.key_fin.payment.repository.PrepareTransferRepository;
import com.finset.key_fin.payment.service.TransferProposalService.ProposalResult;
import com.finset.key_fin.support.SpringIntegrationTestSupport;

@Transactional
@RecordApplicationEvents
@Sql(scripts = "/sql/transfer-proposal-fixture.sql", config = @SqlConfig(encoding = "UTF-8"))
class TransferProposalServiceTest extends SpringIntegrationTestSupport {

	private static final long USER = 986L;

	@Autowired
	private TransferProposalService transferProposalService;
	@Autowired
	private PrepareTransferRepository prepareTransferRepository;
	@Autowired
	private AuditLogRepository auditLogRepository;
	@Autowired
	private JdbcTemplate jdbcTemplate;
	@Autowired
	private ApplicationEvents events;

	@Test
	@DisplayName("오늘·내일 출금 중 부족한 건만 제안: 기존 제안은 금액 갱신, 취소됐던 카드 청구는 다시 제안하지 않음, 준비된 건·만료 건은 취소, 실행된 건은 불변")
	void proposesForShortagesInWindow() {
		ProposalResult result = transferProposalService.propose(USER);

		assertThat(result.incomeAccountFound()).isTrue();
		assertThat(result.created()).isEqualTo(0);
		assertThat(result.updated()).isEqualTo(1);
		assertThat(result.canceled()).isEqualTo(2);

		PrepareTransfer academy = prepareTransferRepository.findById(9901L).orElseThrow();
		assertThat(academy.getStatus()).isEqualTo(TransferStatus.PROPOSED);
		assertThat(academy.getRequiredAmount()).isEqualTo(50000L);

		PrepareTransfer insurance = prepareTransferRepository.findById(9902L).orElseThrow();
		assertThat(insurance.getStatus()).isEqualTo(TransferStatus.CANCELED);
		assertThat(insurance.getFailReason()).isEqualTo(TransferProposalService.REASON_RESOLVED);

		PrepareTransfer expired = prepareTransferRepository.findById(9903L).orElseThrow();
		assertThat(expired.getStatus()).isEqualTo(TransferStatus.CANCELED);
		assertThat(expired.getFailReason()).isEqualTo(TransferProposalService.REASON_EXPIRED);

		assertThat(prepareTransferRepository.findById(9904L).orElseThrow().getStatus()).isEqualTo(TransferStatus.EXECUTED);

		List<PrepareTransfer> open = prepareTransferRepository.findAllByUserIdAndStatusOrderByIdDesc(USER, TransferStatus.PROPOSED);
		assertThat(open).extracting(PrepareTransfer::getId).containsExactly(9901L);
		PrepareTransfer cardBill = prepareTransferRepository.findById(9905L).orElseThrow();
		assertThat(cardBill.getStatus()).isEqualTo(TransferStatus.CANCELED);
		assertThat(cardBill.getRequiredAmount()).isEqualTo(30000L);
		assertThat(cardBill.getFailReason()).isEqualTo(TransferProposalService.REASON_RESOLVED);
		assertThat(academy.getScheduledDate()).isEqualTo(LocalDate.of(2026, 9, 9));
		assertThat(academy.getDueDate()).isEqualTo(LocalDate.of(2026, 9, 10));

		List<AuditLog> logs = auditLogRepository.findAll();
		assertThat(logs).extracting(AuditLog::getAction).containsOnly(AuditAction.CANCEL);
		assertThat(logs).extracting(AuditLog::getTargetId).containsExactlyInAnyOrder("9902", "9903");
	}

	@Test
	@DisplayName("두 번 돌려도 같은 결과 — 제안이 늘지 않는다")
	void idempotentOnRerun() {
		transferProposalService.propose(USER);
		ProposalResult second = transferProposalService.propose(USER);

		assertThat(second.created()).isZero();
		assertThat(second.updated()).isZero();
		assertThat(second.canceled()).isZero();
		assertThat(prepareTransferRepository.findAllByUserIdAndStatusOrderByIdDesc(USER, TransferStatus.PROPOSED)).hasSize(1);
	}

	@Test
	@DisplayName("실패한 제안은 부족액이 남아 있으면 새 번호를 받을 PROPOSED로 되살리고 금액·제안일을 오늘 기준으로 갱신한다")
	void reopensFailedWhenStillShort() {
		markFailed(9905L);

		ProposalResult result = transferProposalService.propose(USER);

		assertThat(result.created()).isEqualTo(1);
		PrepareTransfer reopened = prepareTransferRepository.findById(9905L).orElseThrow();
		assertThat(reopened.isProposed()).isTrue();
		assertThat(reopened.getRequiredAmount()).isEqualTo(80000L);
		assertThat(reopened.getScheduledDate()).isEqualTo(LocalDate.of(2026, 9, 10));
		assertThat(reopened.getInstitutionTxNo()).isNull();
		assertThat(reopened.getFailReason()).isNull();
		assertThat(prepareTransferRepository.findAllByUserIdAndStatusOrderByIdDesc(USER, TransferStatus.PROPOSED))
				.extracting(PrepareTransfer::getId).containsExactly(9905L, 9901L);
	}

	@Test
	@DisplayName("실패한 제안은 부족액이 해소되면 FAILED 기록을 그대로 남기고, 실행된 건과 같은 출금 건에는 새 행을 만들지 않는다")
	void leavesFailedAndExecutedAlone() {
		markFailed(9902L);
		jdbcTemplate.update("UPDATE prepare_transfers SET status = 'EXECUTED', institution_tx_no = '20260910083000000005', "
				+ "executed_at = '2026-09-10 08:31:00', fail_reason = NULL WHERE id = 9905");

		ProposalResult result = transferProposalService.propose(USER);

		assertThat(result.created()).isZero();
		assertThat(result.canceled()).isEqualTo(1);
		PrepareTransfer failed = prepareTransferRepository.findById(9902L).orElseThrow();
		assertThat(failed.getStatus()).isEqualTo(TransferStatus.FAILED);
		assertThat(failed.getFailReason()).isEqualTo("A1014 출금 계좌 잔액 부족");
		assertThat(prepareTransferRepository.findById(9905L).orElseThrow().getStatus()).isEqualTo(TransferStatus.EXECUTED);
		assertThat(prepareTransferRepository.findAllByUserIdOrderByIdDesc(USER)).hasSize(5);
		assertThat(auditLogRepository.findAll()).extracting(AuditLog::getTargetId).containsExactly("9903");
	}

	@Test
	@DisplayName("알림 이벤트: 금액 갱신·취소만 있으면 발행하지 않는다")
	void doesNotPublishWithoutNewProposal() {
		transferProposalService.propose(USER);

		assertThat(events.stream(TransferProposed.class)).isEmpty();
	}

	@Test
	@DisplayName("알림 이벤트: 새 제안과 재개 건이 같은 출금 계좌면 TransferProposed를 한 번만 발행한다")
	void publishesOncePerWithdrawalAccount() {
		jdbcTemplate.update("DELETE FROM prepare_transfers WHERE id = 9901");
		markFailed(9905L);

		ProposalResult result = transferProposalService.propose(USER);

		assertThat(result.created()).isEqualTo(2);
		assertThat(events.stream(TransferProposed.class)).containsExactly(new TransferProposed(USER, 9504L));
	}

	private void markFailed(long id) {
		jdbcTemplate.update("UPDATE prepare_transfers SET status = 'FAILED', institution_tx_no = '20260909083000000009', "
				+ "fail_reason = 'A1014 출금 계좌 잔액 부족' WHERE id = ?", id);
	}

	@Test
	@DisplayName("수입 계좌가 없는 사용자는 제안하지 않는다(만료 정리만)")
	void skipsWithoutIncomeAccount() {
		ProposalResult result = transferProposalService.propose(985L);

		assertThat(result.incomeAccountFound()).isFalse();
		assertThat(result.created()).isZero();
		assertThat(prepareTransferRepository.findAllByUserIdOrderByIdDesc(985L)).isEmpty();
	}
}
