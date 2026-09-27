package com.finset.key_fin.fincoin.dto.response;

import com.finset.key_fin.fincoin.entity.FinCoinReason;
import com.finset.key_fin.fincoin.entity.FinCoin;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.LocalDate;
import java.util.List;

import static io.swagger.v3.oas.annotations.media.Schema.RequiredMode.REQUIRED;

@Schema(name = "FinCoinResponse", description = "ID 내림차순 코인 이력과 다음 페이지 커서")
public record FinCoinResponse(
		@Schema(description = "코인 이력 목록. 이력이 없으면 빈 배열", requiredMode = REQUIRED)
		List<FinCoinHistoryResponse> items,
		@Schema(description = "다음 페이지가 있으면 반환한 마지막 이력 ID, 마지막 페이지는 null",
				types = {"integer", "null"}, format = "int64", requiredMode = REQUIRED)
		Long nextCursor
) {

	public record FinCoinHistoryResponse(
			@Schema(description = "코인 이력 ID", example = "42", requiredMode = REQUIRED)
			Long id,
			@Schema(description = "증감 코인. 적립은 양수, 사용은 음수", example = "-100", requiredMode = REQUIRED)
			Integer delta,
			@Schema(description = "해당 이력 반영 후 잔액", example = "1250", requiredMode = REQUIRED)
			Integer balanceAfter,
			@Schema(description = "지급·사용 사유 코드", example = "PURCHASE", requiredMode = REQUIRED)
			FinCoinReason reasonCode,
			@Schema(description = "사유 설명", example = "아이템 구매", requiredMode = REQUIRED)
			String reasonText,
			@Schema(description = "지급 기준일 (yyyy-MM-dd)", example = "2026-09-10", requiredMode = REQUIRED)
			LocalDate grantDate
	) {

		public static FinCoinHistoryResponse from(FinCoin finCoin) {
			return new FinCoinHistoryResponse(
					finCoin.getId(),
					finCoin.getDelta(),
					finCoin.getBalanceAfter(),
					finCoin.getReasonCode(),
					finCoin.getReasonCode().getReasonText(),
					finCoin.getGrantDate()
			);
		}
	}
}
