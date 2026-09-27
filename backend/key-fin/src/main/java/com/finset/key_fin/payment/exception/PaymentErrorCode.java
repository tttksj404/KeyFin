package com.finset.key_fin.payment.exception;

import org.springframework.http.HttpStatus;

import com.finset.key_fin.global.exception.ErrorCode;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum PaymentErrorCode implements ErrorCode {

	FIXED_EXPENSE_NOT_FOUND(HttpStatus.NOT_FOUND, "PAY_001", "고정지출을 찾을 수 없습니다."),
	FIXED_EXPENSE_SYNCED(HttpStatus.CONFLICT, "PAY_002",
			"금융망에서 동기화된 항목은 KeyFin에서 변경할 수 없습니다. 카드사·서비스에서 변경하면 다음 동기화에 반영됩니다."),
	FIXED_EXPENSE_DUPLICATED(HttpStatus.CONFLICT, "PAY_003", "같은 내용의 고정지출이 이미 등록되어 있습니다."),
	EXPENSE_TYPE_NOT_MANUAL(HttpStatus.BAD_REQUEST, "PAY_004", "카드 청구는 직접 등록할 수 없습니다."),
	TRANSFER_NOT_FOUND(HttpStatus.NOT_FOUND, "PAY_005", "이체 제안을 찾을 수 없습니다."),
	TRANSFER_NOT_PROPOSED(HttpStatus.CONFLICT, "PAY_006", "승인 대기 상태의 제안만 처리할 수 있습니다."),
	TRANSFER_CONSENT_OFF(HttpStatus.FORBIDDEN, "PAY_007", "자동 이체 사전 동의가 꺼져 있습니다. 설정에서 동의 후 이용해 주세요."),
	TRANSFER_LIMIT_ONCE(HttpStatus.FORBIDDEN, "PAY_008", "1회 이체 한도를 초과합니다."),
	TRANSFER_LIMIT_DAILY(HttpStatus.FORBIDDEN, "PAY_009", "1일 이체 한도를 초과합니다."),
	TRANSFER_ACCOUNT_INELIGIBLE(HttpStatus.FORBIDDEN, "PAY_010", "출금 계좌가 수입 계좌·관리 대상이 아닙니다."),
	TRANSFER_INSUFFICIENT_BALANCE(HttpStatus.UNPROCESSABLE_ENTITY, "PAY_011", "출금 계좌 잔액이 부족해 이체에 실패했습니다."),
	TRANSFER_BANK_LIMIT(HttpStatus.UNPROCESSABLE_ENTITY, "PAY_012", "은행 이체 한도를 초과해 이체에 실패했습니다."),
	CARD_NOT_FOUND(HttpStatus.NOT_FOUND, "PAY_013", "카드를 찾을 수 없습니다."),
	FIXED_EXPENSE_NOT_SUBSCRIPTION(HttpStatus.CONFLICT, "PAY_014", "카드 정기결제 항목만 결제 카드를 지정할 수 있습니다."),
	CARD_NOT_MANAGED(HttpStatus.CONFLICT, "PAY_015", "관리 중인 카드만 결제 카드로 지정할 수 있습니다.");

	private final HttpStatus httpStatus;
	private final String code;
	private final String message;
}
