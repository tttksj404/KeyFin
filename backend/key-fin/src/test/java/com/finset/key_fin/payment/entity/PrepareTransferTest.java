package com.finset.key_fin.payment.entity;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.LocalDate;
import java.time.LocalDateTime;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class PrepareTransferTest {

	private static final LocalDate DATE = LocalDate.of(2026, 9, 14);
	private static final LocalDate DUE = LocalDate.of(2026, 9, 15);

	@Test
	@DisplayName("제안 → 승인(번호 채번) → 실행: 상태와 기록이 순서대로 남는다")
	void proposeApproveExecute() {
		PrepareTransfer transfer = PrepareTransfer.proposeForFixedExpense(986L, 9704L, DATE, DUE, 230000L, 9504L, 9505L);

		assertThat(transfer.isProposed()).isTrue();
		assertThat(transfer.getFixedExpenseId()).isEqualTo(9704L);
		assertThat(transfer.getCardBillingId()).isNull();

		transfer.approve("20260915083000000001");
		assertThat(transfer.isApproved()).isTrue();
		assertThat(transfer.getInstitutionTxNo()).isEqualTo("20260915083000000001");

		transfer.markExecuted(LocalDateTime.of(2026, 9, 15, 8, 31));
		assertThat(transfer.getStatus()).isEqualTo(TransferStatus.EXECUTED);
		assertThat(transfer.getExecutedAt()).isEqualTo(LocalDateTime.of(2026, 9, 15, 8, 31));
	}

	@Test
	@DisplayName("승인된 제안이 실패하면 FAILED와 사유가 남고, 제안 상태에서만 취소·금액 갱신, 실패 상태에서만 재개가 가능하다")
	void failAndCancelRules() {
		PrepareTransfer failed = PrepareTransfer.proposeForCardBilling(986L, 9803L, DATE, DATE, 15000L, 9504L, 9505L);
		failed.approve("20260915083000000002");
		failed.markFailed("A1014 잔액 부족");
		assertThat(failed.getStatus()).isEqualTo(TransferStatus.FAILED);
		assertThat(failed.getFailReason()).isEqualTo("A1014 잔액 부족");
		assertThatThrownBy(() -> failed.cancel("만료")).isInstanceOf(IllegalStateException.class);

		PrepareTransfer proposed = PrepareTransfer.proposeForFixedExpense(986L, 9704L, DATE, DUE, 230000L, 9504L, 9505L);
		proposed.updateRequiredAmount(180000L);
		assertThat(proposed.getRequiredAmount()).isEqualTo(180000L);
		proposed.cancel("출금일 경과");
		assertThat(proposed.getStatus()).isEqualTo(TransferStatus.CANCELED);
		assertThatThrownBy(() -> proposed.approve("x")).isInstanceOf(IllegalStateException.class);

		assertThatThrownBy(() -> proposed.reopen(DUE, 70000L)).isInstanceOf(IllegalStateException.class);

		failed.reopen(DUE, 70000L);
		assertThat(failed.isProposed()).isTrue();
		assertThat(failed.getScheduledDate()).isEqualTo(DUE);
		assertThat(failed.getRequiredAmount()).isEqualTo(70000L);
		assertThat(failed.getInstitutionTxNo()).isNull();
		assertThat(failed.getFailReason()).isNull();
		assertThatThrownBy(() -> failed.reopen(DUE, 1L)).isInstanceOf(IllegalStateException.class);
	}

	@Test
	@DisplayName("실행·실패는 승인 상태에서만, 금액 0 이하·동일 계좌·출금일이 실행일보다 앞선 제안은 거부한다")
	void guards() {
		PrepareTransfer proposed = PrepareTransfer.proposeForFixedExpense(986L, 9704L, DATE, DUE, 230000L, 9504L, 9505L);
		assertThatThrownBy(() -> proposed.markExecuted(LocalDateTime.now())).isInstanceOf(IllegalStateException.class);
		assertThatThrownBy(() -> proposed.markFailed("x")).isInstanceOf(IllegalStateException.class);
		assertThatThrownBy(() -> PrepareTransfer.proposeForFixedExpense(986L, 9704L, DATE, DUE, 0L, 9504L, 9505L))
				.isInstanceOf(IllegalArgumentException.class);
		assertThatThrownBy(() -> PrepareTransfer.proposeForFixedExpense(986L, 9704L, DATE, DUE, 1000L, 9504L, 9504L))
				.isInstanceOf(IllegalArgumentException.class);
		assertThatThrownBy(() -> PrepareTransfer.proposeForFixedExpense(986L, 9704L, DUE, DATE, 1000L, 9504L, 9505L))
				.isInstanceOf(IllegalArgumentException.class);
	}
}
