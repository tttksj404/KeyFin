package com.finset.key_fin.link.dto.response;

import io.swagger.v3.oas.annotations.media.Schema;

import java.util.List;

public record LinkCandidatesResponse(
		@Schema(description = "금융망 수시입출금 계좌 후보(KeyFin에 동기화된 행 기준)")
		List<AccountCandidate> accounts,
		@Schema(description = "금융망 카드 후보(KeyFin에 동기화된 행 기준)")
		List<CardCandidate> cards
) {

	public record AccountCandidate(
			@Schema(description = "KeyFin 계좌 ID — 선택 연결·연결 해제·수입 계좌 지정에 사용", example = "3")
			Long id,
			@Schema(description = "금융망 계좌번호", example = "0010011073486799")
			String finAccountNo,
			@Schema(description = "은행 코드", example = "001")
			String bankCode,
			@Schema(description = "은행명", example = "한국은행")
			String bankName,
			@Schema(description = "계좌 잔액(원) — 금융망 실시간 값, 저장하지 않음", example = "1500000")
			Long balance,
			@Schema(description = "KeyFin 관리 대상 여부(is_managed)", example = "false")
			boolean managed
	) {
	}

	public record CardCandidate(
			@Schema(description = "KeyFin 카드 ID — 선택 연결·연결 해제에 사용", example = "7")
			Long id,
			@Schema(description = "카드번호", example = "1003198565339181")
			String cardNo,
			@Schema(description = "카드사명", example = "롯데카드")
			String issuerName,
			@Schema(description = "카드명", example = "디지로카 SEOUL")
			String cardName,
			@Schema(description = "청구 출금 계좌번호", example = "0323555042323510")
			String withdrawalAccountNo,
			@Schema(description = "KeyFin 관리 대상 여부(is_managed)", example = "true")
			boolean managed
	) {
	}
}
