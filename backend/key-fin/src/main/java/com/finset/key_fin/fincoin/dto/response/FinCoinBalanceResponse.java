package com.finset.key_fin.fincoin.dto.response;

import io.swagger.v3.oas.annotations.media.Schema;

import static io.swagger.v3.oas.annotations.media.Schema.RequiredMode.REQUIRED;

@Schema(description = "현재 코인 잔액")
public record FinCoinBalanceResponse(
		@Schema(description = "최신 이력 반영 후 잔액. 이력이 없으면 0", example = "1250", requiredMode = REQUIRED)
		Integer balance
) {
}
