package com.finset.key_fin.payment.dto.request;

import com.finset.key_fin.payment.entity.ExpenseType;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

@Schema(description = "고정지출 등록·수정 요청 — 수정은 전체 교체")
public record FixedExpenseRequest(
		@Schema(description = "지출명", example = "월세", maxLength = 50)
		@NotBlank
		@Size(max = 50)
		String name,

		@Schema(description = "지출 유형 — RENT/SUBSCRIPTION/UTILITY/LOAN (CARD_BILL은 직접 등록 불가)", example = "RENT")
		@NotNull
		ExpenseType expenseType,

		@Schema(description = "금액(원). 변동형은 예상액", example = "550000")
		@NotNull
		@Min(1)
		Long amount,

		@Schema(description = "변동형 여부", example = "false")
		boolean isVariable,

		@Schema(description = "출금일 1~31 — 없는 날짜는 해당 월 말일로 보정", example = "15")
		@NotNull
		@Min(1)
		@Max(31)
		Integer paymentDay,

		@Schema(description = "출금 계좌 ID — 본인의 관리 대상 계좌", example = "3")
		@NotNull
		Long withdrawalAccountId
) {
}
