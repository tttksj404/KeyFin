package com.finset.key_fin.transaction.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record TransactionMemoUpdateRequest(
		@Schema(
				description = "거래 메모. 빈 문자열 또는 공백만 입력하면 기존 메모를 삭제합니다.",
				example = "회식 — 회사에서 정산 예정",
				requiredMode = Schema.RequiredMode.REQUIRED
		)
		@NotNull(message = "거래 메모는 필수입니다.")
		@Size(max = 255, message = "거래 메모는 255자 이하여야 합니다.")
		String memo
) {
}
