package com.finset.key_fin.link.exception;

import com.finset.key_fin.global.exception.ErrorCode;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

@Getter
@RequiredArgsConstructor
public enum LinkErrorCode implements ErrorCode {

	FINANCE_MEMBER_ALREADY_LINKED(
			HttpStatus.CONFLICT,
			"LINK_001",
			"해당 금융망 사용자는 이미 다른 계정과 연결되어 있습니다."
	),
	FINANCE_NOT_CONNECTED(
			HttpStatus.CONFLICT,
			"LINK_002",
			"금융망 연결이 필요합니다. 먼저 금융망 회원을 연결해 주세요."
	),
	EMPTY_LINK_REQUEST(
			HttpStatus.BAD_REQUEST,
			"LINK_003",
			"연결할 계좌 또는 카드를 하나 이상 선택해 주세요."
	),
	ACCOUNT_NOT_FOUND(
			HttpStatus.NOT_FOUND,
			"LINK_004",
			"계좌를 찾을 수 없습니다. 후보 목록을 다시 조회해 주세요."
	),
	CARD_NOT_FOUND(
			HttpStatus.NOT_FOUND,
			"LINK_005",
			"카드를 찾을 수 없습니다. 후보 목록을 다시 조회해 주세요."
	);

	private final HttpStatus httpStatus;
	private final String code;
	private final String message;
}
