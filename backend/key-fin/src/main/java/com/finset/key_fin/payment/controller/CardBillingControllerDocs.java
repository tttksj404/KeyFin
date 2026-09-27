package com.finset.key_fin.payment.controller;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.payment.dto.response.CardBillingDetailResponse;
import com.finset.key_fin.payment.dto.response.CardBillingSummaryResponse;

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
		name = "카드 청구",
		description = "카드별 청구 예정액(이번 주 승인 누적, 아직 청구서 없음)과 발행된 청구서(확정)를 조회합니다. "
				+ "금융망 규칙: 월~일 승인은 다음 월요일 07:30에 청구서로 발행되고, 카드의 출금 요일 16:00에 출금됩니다."
)
public interface CardBillingControllerDocs {

	@Operation(
			summary = "카드별 청구 요약",
			description = "관리 대상 카드마다 이번 주기(cycleFrom = 이번 주 월요일 ~ asOf) LIVE 승인 합계(estimated.amount)·건수와 "
					+ "예정 출금일(nextBillingDate + 출금 요일 − 1), 가장 최근 청구서 1건을 돌려줍니다. "
					+ "estimated는 예상값이고 latestStatement는 발행된 확정값입니다. "
					+ "withdrawalWeekday가 null인 카드(출금 요일 미저장, 재연결 필요)는 예정 출금일과 청구서 출금일이 null이며 캘린더에는 나타나지 않습니다. "
					+ "청구서가 없으면 latestStatement가 null, 승인이 없으면 estimated.amount 0·approvalCount 0입니다.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(
					responseCode = "200",
					description = "조회 성공",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = @ExampleObject(
									name = "카드 2장",
									value = "{\"success\":true,\"code\":\"SUCCESS\",\"message\":\"요청이 성공했습니다.\",\"data\":{\"asOf\":\"2026-09-16\",\"cycleFrom\":\"2026-09-14\",\"nextBillingDate\":\"2026-09-21\",\"cards\":[{\"cardId\":3,\"cardName\":\"신한 테스트카드\",\"withdrawalWeekday\":3,\"withdrawalAccountId\":5,\"estimated\":{\"amount\":15000,\"approvalCount\":2,\"withdrawalDate\":\"2026-09-23\"},\"latestStatement\":{\"billingId\":12,\"billingDate\":\"2026-09-14\",\"amount\":80000,\"status\":\"UNPAID\",\"withdrawalDate\":\"2026-09-16\",\"paidAt\":null}},{\"cardId\":4,\"cardName\":\"KB 테스트카드\",\"withdrawalWeekday\":null,\"withdrawalAccountId\":5,\"estimated\":{\"amount\":0,\"approvalCount\":0,\"withdrawalDate\":null},\"latestStatement\":null}]}}"
							)
					)
			),
			@ApiResponse(responseCode = "401", description = "Access Token이 없거나 유효하지 않음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	})
	BaseResponse<CardBillingSummaryResponse> summary(Long userId);

	@Operation(
			summary = "카드 청구 상세",
			description = "카드 한 장의 예정액과 그 근거(이번 주기 LIVE 승인 목록, 최신순 — 취소 거래 제외), 발행 청구서 목록을 돌려줍니다. "
					+ "from·to는 청구서 발행 월(yyyyMM), 생략하면 전월~이번 달, 최대 12개월. "
					+ "카드를 연결한 달의 전월 이전 청구서는 동기화 대상이 아니라 조회되지 않습니다. "
					+ "approvals의 merchantName은 거래 원문입니다.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(
					responseCode = "200",
					description = "조회 성공",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = @ExampleObject(
									name = "기본 범위",
									value = "{\"success\":true,\"code\":\"SUCCESS\",\"message\":\"요청이 성공했습니다.\",\"data\":{\"asOf\":\"2026-09-16\",\"cycleFrom\":\"2026-09-14\",\"nextBillingDate\":\"2026-09-21\",\"cardId\":3,\"cardName\":\"신한 테스트카드\",\"withdrawalWeekday\":3,\"withdrawalAccountId\":5,\"estimated\":{\"amount\":15000,\"withdrawalDate\":\"2026-09-23\",\"approvals\":[{\"transactionId\":502,\"date\":\"2026-09-15\",\"merchantName\":\"GS25 역삼점\",\"amount\":6000},{\"transactionId\":501,\"date\":\"2026-09-14\",\"merchantName\":\"메가커피\",\"amount\":9000}]},\"from\":\"202608\",\"to\":\"202609\",\"statements\":[{\"billingId\":12,\"billingDate\":\"2026-09-14\",\"amount\":80000,\"status\":\"UNPAID\",\"withdrawalDate\":\"2026-09-16\",\"paidAt\":null},{\"billingId\":9,\"billingDate\":\"2026-08-31\",\"amount\":30000,\"status\":\"PAID\",\"withdrawalDate\":\"2026-09-02\",\"paidAt\":\"2026-09-02T16:00:00\"}]}}"
							)
					)
			),
			@ApiResponse(responseCode = "400", description = "from·to가 yyyyMM이 아니거나 역순·12개월 초과(COMMON_001)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "404", description = "본인 카드가 아니거나 없음(PAY_013)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "401", description = "Access Token이 없거나 유효하지 않음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	})
	BaseResponse<CardBillingDetailResponse> detail(
			Long userId,
			long cardId,
			@Parameter(description = "청구서 발행 월 시작(선택). yyyyMM, 기본 to의 전월", example = "202608")
			String from,
			@Parameter(description = "청구서 발행 월 끝(선택). yyyyMM, 기본 이번 달", example = "202609")
			String to
	);
}
