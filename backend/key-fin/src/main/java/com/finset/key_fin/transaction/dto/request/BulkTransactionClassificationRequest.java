package com.finset.key_fin.transaction.dto.request;

import com.finset.key_fin.transaction.entity.ExcludeTag;
import io.swagger.v3.oas.annotations.media.ArraySchema;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;

import java.util.List;

public record BulkTransactionClassificationRequest(
		@ArraySchema(
				arraySchema = @Schema(description = "분류 확정 항목 목록", requiredMode = Schema.RequiredMode.REQUIRED),
				minItems = 1,
				maxItems = 100
		)
		@NotEmpty(message = "분류 확정 항목은 한 건 이상이어야 합니다.")
		@Size(max = 100, message = "분류 확정 항목은 최대 100건까지 처리할 수 있습니다.")
		List<@Valid Item> items
) {

	public record Item(
			@Schema(description = "거래 ID", example = "501", requiredMode = Schema.RequiredMode.REQUIRED)
			@NotNull(message = "거래 ID는 필수입니다.")
			@Positive(message = "거래 ID는 0보다 커야 합니다.")
			Long transactionId,

			@Schema(description = "세분류 ID. 일반 소비는 단독 입력하고 RESTORE는 excludeTag와 함께 입력", example = "102", nullable = true)
			@Positive(message = "세분류 ID는 0보다 커야 합니다.")
			Integer subcategoryId,

			@Schema(
					description = "제외 태그. DUTCH(더치페이), SELF_TRANSFER(내 계좌 이동), "
							+ "BUDGET_EXCLUDED(예산에서 제외), EMERGENCY(비상금) 또는 RESTORE(환급 입금)",
					example = "DUTCH",
					allowableValues = {"DUTCH", "SELF_TRANSFER", "BUDGET_EXCLUDED", "EMERGENCY", "RESTORE"},
					nullable = true
			)
			ExcludeTag excludeTag,

			@Schema(description = "더치페이 실제 부담액. DUTCH일 때만 필수", example = "15000", nullable = true)
			@Positive(message = "더치페이 실제 부담액은 0보다 커야 합니다.")
			Long adjustedAmount
	) {
		public TransactionClassificationRequest toClassificationRequest() {
			return new TransactionClassificationRequest(subcategoryId, excludeTag, adjustedAmount);
		}
	}
}
