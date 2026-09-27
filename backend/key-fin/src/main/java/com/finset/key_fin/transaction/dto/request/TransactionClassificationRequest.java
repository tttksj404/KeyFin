package com.finset.key_fin.transaction.dto.request;

import com.finset.key_fin.transaction.entity.ExcludeTag;
import io.swagger.v3.oas.annotations.media.Schema;

public record TransactionClassificationRequest(
		@Schema(description = "확정할 세분류 ID. 환급(RESTORE)은 excludeTag와 함께 입력", example = "102", nullable = true)
		Integer subcategoryId,
		@Schema(
				description = "거래 처리 태그. DUTCH(더치페이), SELF_TRANSFER(내 계좌 이동), "
						+ "BUDGET_EXCLUDED(예산에서 제외), EMERGENCY(비상금) 또는 환급 입금의 RESTORE",
				example = "DUTCH",
				allowableValues = {"DUTCH", "SELF_TRANSFER", "BUDGET_EXCLUDED", "EMERGENCY", "RESTORE"},
				nullable = true
		)
		ExcludeTag excludeTag,
		@Schema(description = "더치페이 실제 부담액. DUTCH일 때만 필수", example = "15000", nullable = true)
		Long adjustedAmount
) {
}
