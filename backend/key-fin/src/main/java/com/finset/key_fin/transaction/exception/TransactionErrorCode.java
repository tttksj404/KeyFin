package com.finset.key_fin.transaction.exception;

import com.finset.key_fin.global.exception.ErrorCode;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

@Getter
@RequiredArgsConstructor
public enum TransactionErrorCode implements ErrorCode {

	INVALID_MONTH(HttpStatus.BAD_REQUEST, "TRANSACTION_001", "조회 월 형식이 올바르지 않습니다."),
	INVALID_PAGE_SIZE(HttpStatus.BAD_REQUEST, "TRANSACTION_002", "페이지 크기는 1 이상 100 이하여야 합니다."),
	INVALID_SEARCH_FILTER(HttpStatus.BAD_REQUEST, "TRANSACTION_003", "거래 조회 조건이 올바르지 않습니다."),
	TRANSACTION_NOT_FOUND(HttpStatus.NOT_FOUND, "TRANSACTION_004", "거래를 찾을 수 없습니다."),
	SUBCATEGORY_NOT_FOUND(HttpStatus.NOT_FOUND, "TRANSACTION_005", "세분류를 찾을 수 없습니다."),
	INVALID_CLASSIFICATION(HttpStatus.BAD_REQUEST, "TRANSACTION_006", "거래 분류 요청이 올바르지 않습니다."),
	CLASSIFICATION_NOT_ALLOWED(HttpStatus.CONFLICT, "TRANSACTION_007", "분류할 수 없는 거래입니다."),
	INVALID_ADJUSTED_AMOUNT(HttpStatus.BAD_REQUEST, "TRANSACTION_008", "더치페이 실제 부담액이 올바르지 않습니다.");

	private final HttpStatus httpStatus;
	private final String code;
	private final String message;
}
