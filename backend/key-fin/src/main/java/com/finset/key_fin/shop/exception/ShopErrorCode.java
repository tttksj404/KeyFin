package com.finset.key_fin.shop.exception;

import com.finset.key_fin.global.exception.ErrorCode;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

@Getter
@RequiredArgsConstructor
public enum ShopErrorCode implements ErrorCode {
	ITEM_NOT_FOUND(HttpStatus.NOT_FOUND, "SHOP_001", "판매 중인 상품을 찾을 수 없습니다."),
	ITEM_ALREADY_OWNED(HttpStatus.CONFLICT, "SHOP_002", "이미 보유한 상품입니다."),
	INSUFFICIENT_COINS(HttpStatus.CONFLICT, "SHOP_003", "코인이 부족합니다."),
	INVALID_ITEM_PRICE(HttpStatus.INTERNAL_SERVER_ERROR, "SHOP_004", "상품 가격이 올바르지 않습니다.");

	private final HttpStatus httpStatus;
	private final String code;
	private final String message;
}
