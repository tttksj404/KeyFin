package com.finset.key_fin.budget.exception;

import org.springframework.http.HttpStatus;

import com.finset.key_fin.global.exception.ErrorCode;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum BudgetErrorCode implements ErrorCode {

	BUDGET_ALREADY_EXISTS(HttpStatus.CONFLICT, "BUDGET_001", "해당 월의 예산이 이미 존재합니다."),
	BUDGET_NOT_FOUND(HttpStatus.NOT_FOUND, "BUDGET_002", "예산을 찾을 수 없습니다."),
	BUDGET_ALREADY_CONFIRMED(HttpStatus.CONFLICT, "BUDGET_003", "이미 확정된 예산은 변경할 수 없습니다."),
	ENVELOPE_MISMATCH(HttpStatus.BAD_REQUEST, "BUDGET_004", "요청 봉투 목록이 예산의 봉투 구성과 일치하지 않습니다."),
	AMOUNT_NOT_THOUSAND_UNIT(HttpStatus.BAD_REQUEST, "BUDGET_005", "예산 금액은 1,000원 단위여야 합니다.");

	private final HttpStatus httpStatus;
	private final String code;
	private final String message;
}
