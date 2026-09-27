package com.finset.key_fin.payment.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;

import com.finset.key_fin.support.SpringIntegrationTestSupport;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlConfig;
import org.springframework.transaction.annotation.Transactional;

import com.finset.key_fin.account.exception.AccountErrorCode;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.exception.ErrorCode;
import com.finset.key_fin.payment.dto.request.FixedExpenseRequest;
import com.finset.key_fin.payment.dto.response.FixedExpenseIdResponse;
import com.finset.key_fin.payment.dto.response.FixedExpenseResponse;
import com.finset.key_fin.payment.entity.ExpenseType;
import com.finset.key_fin.payment.entity.FixedExpense;
import com.finset.key_fin.payment.exception.PaymentErrorCode;
import com.finset.key_fin.payment.repository.FixedExpenseRepository;

@Transactional
@Sql(scripts = "/sql/fixed-expense-fixture.sql", config = @SqlConfig(encoding = "UTF-8"))
class FixedExpenseServiceTest extends SpringIntegrationTestSupport {

	private static final long OWNER = 988L;
	private static final long OTHER_USER = 987L;
	private static final long MANAGED_ACCOUNT = 9501L;
	private static final long UNMANAGED_ACCOUNT = 9502L;
	private static final long OTHERS_ACCOUNT = 9503L;
	private static final long MANUAL_RENT = 9601L;
	private static final long SYNCED_SUBSCRIPTION = 9602L;
	private static final long DELETED_GYM = 9603L;
	private static final long MANAGED_CARD = 9701L;
	private static final long UNMANAGED_CARD = 9702L;
	private static final long OTHERS_CARD = 9703L;

	@Autowired
	private FixedExpenseService fixedExpenseService;

	@Autowired
	private FixedExpenseRepository fixedExpenseRepository;

	@Test
	@DisplayName("관리 계좌로 고정지출을 등록하면 활성·수동(fin_subscription_id 없음) 행이 생긴다")
	void registerManualExpense() {
		FixedExpenseIdResponse response = fixedExpenseService.register(OWNER,
				request("통신비", ExpenseType.UTILITY, 45000L, true, 25, MANAGED_ACCOUNT));

		FixedExpense saved = fixedExpenseRepository.findById(response.id()).orElseThrow();
		assertThat(saved.getUser().getId()).isEqualTo(OWNER);
		assertThat(saved.getExpenseType()).isEqualTo(ExpenseType.UTILITY);
		assertThat(saved.isVariable()).isTrue();
		assertThat(saved.getPaymentDay()).isEqualTo(25);
		assertThat(saved.isSynced()).isFalse();
		assertThat(saved.isActive()).isTrue();
	}

	@Test
	@DisplayName("삭제된 항목과 같은 내용은 다시 등록할 수 있고, 새 행으로 만들어진다 (되살리기 아님)")
	void reRegisterAfterDeleteCreatesNewRow() {
		FixedExpenseIdResponse response = fixedExpenseService.register(OWNER,
				request("헬스장", ExpenseType.SUBSCRIPTION, 60000L, false, 1, MANAGED_ACCOUNT));

		assertThat(response.id()).isNotEqualTo(DELETED_GYM);
		assertThat(fixedExpenseRepository.findById(DELETED_GYM).orElseThrow().isActive()).isFalse();
	}

	@Test
	@DisplayName("활성 항목과 이름·유형·금액·출금일·계좌가 모두 같으면 FIXED_EXPENSE_DUPLICATED")
	void rejectExactDuplicate() {
		assertError(() -> fixedExpenseService.register(OWNER,
				request("월세", ExpenseType.RENT, 550000L, false, 15, MANAGED_ACCOUNT)),
				PaymentErrorCode.FIXED_EXPENSE_DUPLICATED);
	}

	@Test
	@DisplayName("CARD_BILL은 직접 등록할 수 없다")
	void rejectCardBill() {
		assertError(() -> fixedExpenseService.register(OWNER,
				request("카드값", ExpenseType.CARD_BILL, 300000L, true, 25, MANAGED_ACCOUNT)),
				PaymentErrorCode.EXPENSE_TYPE_NOT_MANUAL);
	}

	@Test
	@DisplayName("타인 계좌는 ACCOUNT_NOT_FOUND, 본인의 미관리 계좌는 ACCOUNT_NOT_MANAGED")
	void rejectInvalidWithdrawalAccount() {
		assertError(() -> fixedExpenseService.register(OWNER,
				request("월세", ExpenseType.RENT, 500000L, false, 15, OTHERS_ACCOUNT)),
				AccountErrorCode.ACCOUNT_NOT_FOUND);
		assertError(() -> fixedExpenseService.register(OWNER,
				request("월세", ExpenseType.RENT, 500000L, false, 15, UNMANAGED_ACCOUNT)),
				AccountErrorCode.ACCOUNT_NOT_MANAGED);
	}

	@Test
	@DisplayName("목록은 본인의 활성 항목만 id 순으로, 동기화 항목은 synced=true")
	void listActiveOnly() {
		List<FixedExpenseResponse> list = fixedExpenseService.list(OWNER);

		assertThat(list).extracting(FixedExpenseResponse::id).containsExactly(MANUAL_RENT, SYNCED_SUBSCRIPTION);
		assertThat(list.get(0).synced()).isFalse();
		assertThat(list.get(1).synced()).isTrue();
	}

	@Test
	@DisplayName("수정은 바디 전체로 교체된다")
	void updateReplacesAllFields() {
		fixedExpenseService.update(OWNER, MANUAL_RENT,
				request("월세(인상)", ExpenseType.RENT, 600000L, false, 20, MANAGED_ACCOUNT));

		FixedExpense updated = fixedExpenseRepository.findById(MANUAL_RENT).orElseThrow();
		assertThat(updated.getName()).isEqualTo("월세(인상)");
		assertThat(updated.getAmount()).isEqualTo(600000L);
		assertThat(updated.getPaymentDay()).isEqualTo(20);
	}

	@Test
	@DisplayName("삭제는 행을 지우지 않고 비활성화하며, 이후 수정·삭제·목록에서 사라진다")
	void deleteDeactivates() {
		fixedExpenseService.delete(OWNER, MANUAL_RENT);

		assertThat(fixedExpenseRepository.findById(MANUAL_RENT).orElseThrow().isActive()).isFalse();
		assertThat(fixedExpenseService.list(OWNER)).extracting(FixedExpenseResponse::id)
				.doesNotContain(MANUAL_RENT);
		assertError(() -> fixedExpenseService.update(OWNER, MANUAL_RENT,
				request("월세", ExpenseType.RENT, 550000L, false, 15, MANAGED_ACCOUNT)),
				PaymentErrorCode.FIXED_EXPENSE_NOT_FOUND);
		assertError(() -> fixedExpenseService.delete(OWNER, MANUAL_RENT), PaymentErrorCode.FIXED_EXPENSE_NOT_FOUND);
	}

	@Test
	@DisplayName("금융망 동기화 항목은 수정·삭제 모두 FIXED_EXPENSE_SYNCED")
	void rejectChangesToSyncedExpense() {
		assertError(() -> fixedExpenseService.update(OWNER, SYNCED_SUBSCRIPTION,
				request("FLO 개인", ExpenseType.SUBSCRIPTION, 9900L, false, 15, MANAGED_ACCOUNT)),
				PaymentErrorCode.FIXED_EXPENSE_SYNCED);
		assertError(() -> fixedExpenseService.delete(OWNER, SYNCED_SUBSCRIPTION), PaymentErrorCode.FIXED_EXPENSE_SYNCED);
		assertThat(fixedExpenseRepository.findById(SYNCED_SUBSCRIPTION).orElseThrow().isActive()).isTrue();
	}

	@Test
	@DisplayName("타인의 고정지출은 존재를 드러내지 않고 FIXED_EXPENSE_NOT_FOUND")
	void rejectOtherUsersExpense() {
		assertError(() -> fixedExpenseService.delete(OTHER_USER, MANUAL_RENT), PaymentErrorCode.FIXED_EXPENSE_NOT_FOUND);
	}

	@Test
	@DisplayName("금융망 정기결제에 본인 관리 카드를 지정하면 저장되고 목록에 cardId로 나온다")
	void assignCardToSyncedSubscription() {
		fixedExpenseService.assignCard(OWNER, SYNCED_SUBSCRIPTION, MANAGED_CARD);

		assertThat(fixedExpenseRepository.findById(SYNCED_SUBSCRIPTION).orElseThrow().getCardId()).isEqualTo(MANAGED_CARD);
		assertThat(fixedExpenseService.list(OWNER))
				.filteredOn(FixedExpenseResponse::synced)
				.extracting(FixedExpenseResponse::cardId)
				.containsExactly(MANAGED_CARD);
	}

	@Test
	@DisplayName("결제 카드 지정은 본인 활성 정기결제와 본인 관리 카드만 허용한다")
	void rejectInvalidCardAssignment() {
		assertError(() -> fixedExpenseService.assignCard(OWNER, MANUAL_RENT, MANAGED_CARD),
				PaymentErrorCode.FIXED_EXPENSE_NOT_SUBSCRIPTION);
		assertError(() -> fixedExpenseService.assignCard(OTHER_USER, SYNCED_SUBSCRIPTION, OTHERS_CARD),
				PaymentErrorCode.FIXED_EXPENSE_NOT_FOUND);
		assertError(() -> fixedExpenseService.assignCard(OWNER, SYNCED_SUBSCRIPTION, OTHERS_CARD),
				PaymentErrorCode.CARD_NOT_FOUND);
		assertError(() -> fixedExpenseService.assignCard(OWNER, SYNCED_SUBSCRIPTION, UNMANAGED_CARD),
				PaymentErrorCode.CARD_NOT_MANAGED);
	}

	private static FixedExpenseRequest request(String name, ExpenseType type, Long amount, boolean variable,
			int paymentDay, long accountId) {
		return new FixedExpenseRequest(name, type, amount, variable, paymentDay, accountId);
	}

	private static void assertError(Runnable action, ErrorCode expected) {
		assertThatThrownBy(action::run)
				.isInstanceOf(BusinessException.class)
				.extracting(e -> ((BusinessException) e).getErrorCode())
				.isEqualTo(expected);
	}
}
