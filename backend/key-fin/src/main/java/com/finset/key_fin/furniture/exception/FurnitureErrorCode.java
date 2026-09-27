package com.finset.key_fin.furniture.exception;

import com.finset.key_fin.global.exception.ErrorCode;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

@Getter
@RequiredArgsConstructor
public enum FurnitureErrorCode implements ErrorCode {
	USER_FURNITURE_NOT_FOUND(HttpStatus.NOT_FOUND, "FURNITURE_001", "보유 가구를 찾을 수 없습니다."),
	PLACEMENT_NOT_ALLOWED(HttpStatus.BAD_REQUEST, "FURNITURE_002", "가구를 설치할 수 없는 면입니다."),
	DEFAULT_FURNITURE_CANNOT_UNPLACE(HttpStatus.CONFLICT, "FURNITURE_003", "필수 가구는 단독으로 설치 해제할 수 없습니다."),
	ESSENTIAL_FURNITURE_COUNT_INVALID(HttpStatus.CONFLICT, "FURNITURE_004", "소파, TV, 식탁, 커피테이블은 각각 하나씩 설치해야 합니다.");

	private final HttpStatus httpStatus;
	private final String code;
	private final String message;
}
