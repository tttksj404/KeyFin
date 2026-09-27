package com.finset.key_fin.fincoin.entity;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum FinCoinReason {
	ATTEND("출석 보상"),
	CONFIRM_ALL("거래 내역 전체 확인 보상"),
	WEEKLY("주간 보상"),
	MONTHLY("월간 보상"),
	PURCHASE("아이템 구매");

	private final String reasonText;
}
