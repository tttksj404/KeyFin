package com.finset.key_fin.payment.controller;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

import java.time.YearMonth;

import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.payment.dto.response.PaymentCalendarResponse;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.ExampleObject;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;

@Tag(
		name = "결제 준비",
		description = "정기 지출 통합 일정과 결제일 전 자금 준비를 제공합니다."
)
public interface PaymentCalendarControllerDocs {

	@Operation(
			summary = "정기 지출 통합 일정(캘린더)",
			description = "달력 월(yyyyMM, 생략 시 이번 달)의 출금 예정을 날짜별로 반환합니다. "
					+ "호출 시 금융망 정기결제 목록을 먼저 동기화하며, 동기화가 실패해도 저장된 항목으로 응답합니다. "
					+ "type: FIXED = 직접 등록한 고정지출(출금 계좌에서 나감) / CARD_SUBSCRIPTION = 금융망 카드 정기결제(카드 청구에 포함, withdrawalAccountId null) / CARD_BILL = 카드 청구(발행된 주 단위 청구서는 정확 금액, 이번 주 승인 합계는 estimated=true로 다음 출금일에 표시; cardId 포함). "
					+ "출금일이 없는 달(29~31일)은 말일로 보정. estimated=true는 변동형 예상액·미발행 청구 예정액. prepared/shortage는 출금 계좌 잔액 스냅샷을 같은 계좌의 오늘 이후 항목에 날짜순으로 차감한 판정(FR-PAY-02) — 출금 계좌 없음·과거 항목은 null, 결제완료 청구는 true/0. "
					+ "같은 날 정렬: FIXED → CARD_SUBSCRIPTION, 금액 내림차순.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(
					responseCode = "200",
					description = "조회 성공 (항목 없는 달은 days 빈 배열)",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = @ExampleObject(
									name = "9월 일정",
									value = "{\"success\":true,\"code\":\"SUCCESS\",\"message\":\"요청이 성공했습니다.\",\"data\":{\"month\":\"202609\",\"days\":[{\"date\":\"2026-09-15\",\"items\":[{\"type\":\"FIXED\",\"fixedExpenseId\":7,\"cardId\":null,\"name\":\"월세\",\"expenseType\":\"RENT\",\"amount\":550000,\"estimated\":false,\"withdrawalAccountId\":3,\"prepared\":true,\"shortage\":0},{\"type\":\"CARD_SUBSCRIPTION\",\"fixedExpenseId\":8,\"cardId\":null,\"name\":\"FLO\",\"expenseType\":\"SUBSCRIPTION\",\"amount\":8900,\"estimated\":false,\"withdrawalAccountId\":null,\"prepared\":null,\"shortage\":null}]},{\"date\":\"2026-09-16\",\"items\":[{\"type\":\"CARD_BILL\",\"fixedExpenseId\":null,\"cardId\":2,\"name\":\"KB 국민카드\",\"expenseType\":\"CARD_BILL\",\"amount\":83900,\"estimated\":true,\"withdrawalAccountId\":3,\"prepared\":false,\"shortage\":33900}]},{\"date\":\"2026-09-30\",\"items\":[{\"type\":\"FIXED\",\"fixedExpenseId\":9,\"cardId\":null,\"name\":\"통신비\",\"expenseType\":\"UTILITY\",\"amount\":45000,\"estimated\":true,\"withdrawalAccountId\":3,\"prepared\":false,\"shortage\":45000}]}]}}"
							)
					)
			),
			@ApiResponse(
					responseCode = "400",
					description = "month 형식 오류 (yyyyMM 아님)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "401",
					description = "Access Token이 없거나 유효하지 않음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "500",
					description = "서버 내부 오류",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			)
	})
	BaseResponse<PaymentCalendarResponse> getCalendar(
			Long userId,
			@Parameter(description = "달력 월 yyyyMM. 생략 시 이번 달", example = "202609") YearMonth month
	);
}
