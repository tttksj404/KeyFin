package com.finset.key_fin.transaction.dto.response;

import io.swagger.v3.oas.annotations.media.Schema;

public record BulkTransactionClassificationResponse(
		@Schema(description = "확정 처리된 거래 수", example = "2")
		int confirmed,

		@Schema(description = "처리 후 남은 미확정 거래 수", example = "0")
		long pendingRemain
) {
}
