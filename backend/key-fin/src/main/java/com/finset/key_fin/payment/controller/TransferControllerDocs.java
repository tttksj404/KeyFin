package com.finset.key_fin.payment.controller;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.payment.dto.response.TransferApproveResponse;
import com.finset.key_fin.payment.dto.response.TransferDetailResponse;
import com.finset.key_fin.payment.dto.response.TransferListResponse;
import com.finset.key_fin.payment.entity.TransferStatus;

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
		name = "결제 준비 이체",
		description = "부족한 출금 건에 대한 이체 제안(08:30 배치)을 조회하고, 사용자 승인으로 수입 계좌 → 출금 계좌 이체를 실행합니다. "
				+ "승인 없이 실행되는 경로는 없으며, 재시도는 같은 기관거래고유번호로 이루어져 이중 이체가 발생하지 않습니다."
)
public interface TransferControllerDocs {

	@Operation(
			summary = "이체 제안·이력 목록",
			description = "status·month(대상 출금일 기준 yyyyMM)로 거르고, 생략하면 전체를 최신순으로 돌려줍니다. "
					+ "cursor는 직전 응답의 nextCursor(없으면 첫 페이지), size는 1~100(기본 20). nextCursor가 null이면 마지막 페이지. "
					+ "PROPOSED = 승인 대기 / APPROVED = 실행 중(응답 대기, 다시 승인하면 같은 번호로 재시도) / EXECUTED = 실행 완료 / "
					+ "FAILED = 금융망 거부(잔액 부족·은행 한도) / CANCELED = 출금일 경과 또는 부족액 해소로 무효. "
					+ "scheduledDate는 실행 예정일(제안한 날), dueDate는 대상 출금일. purpose.type은 FIXED(고정지출) 또는 CARD_BILL(카드 청구서).",
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
									name = "승인 대기 목록",
									value = "{\"success\":true,\"code\":\"SUCCESS\",\"message\":\"요청이 성공했습니다.\",\"data\":{\"items\":[{\"id\":21,\"status\":\"PROPOSED\",\"scheduledDate\":\"2026-09-14\",\"dueDate\":\"2026-09-15\",\"requiredAmount\":230000,\"fromAccountId\":1,\"toAccountId\":3,\"purpose\":{\"type\":\"FIXED\",\"fixedExpenseId\":7,\"cardBillingId\":null,\"name\":\"월세\"},\"executedAt\":null,\"failReason\":null,\"createdAt\":\"2026-09-14T08:30:12\"},{\"id\":22,\"status\":\"PROPOSED\",\"scheduledDate\":\"2026-09-14\",\"dueDate\":\"2026-09-14\",\"requiredAmount\":33900,\"fromAccountId\":1,\"toAccountId\":3,\"purpose\":{\"type\":\"CARD_BILL\",\"fixedExpenseId\":null,\"cardBillingId\":5,\"name\":\"KB 국민카드\"},\"executedAt\":null,\"failReason\":null,\"createdAt\":\"2026-09-14T08:30:12\"}],\"nextCursor\":null}}"
							)
					)
			),
			@ApiResponse(responseCode = "400", description = "status·month·cursor·size 값이 올바르지 않음(COMMON_001)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "401", description = "Access Token이 없거나 유효하지 않음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	})
	BaseResponse<TransferListResponse> list(
			Long userId,
			@Parameter(description = "상태 필터(선택). PROPOSED / APPROVED / EXECUTED / FAILED / CANCELED", example = "PROPOSED")
			TransferStatus status,
			@Parameter(description = "대상 출금일 월 필터(선택). yyyyMM", example = "202609")
			String month,
			@Parameter(description = "직전 응답의 nextCursor(선택). 생략하면 첫 페이지", example = "21")
			Long cursor,
			@Parameter(description = "페이지 크기(선택). 1~100, 기본 20", example = "20")
			Integer size
	);

	@Operation(
			summary = "이체 상세·이력 타임라인",
			description = "제안 한 건의 현재 상태(목록 항목과 같은 필드)와 감사 로그 타임라인을 돌려줍니다. "
					+ "history의 action은 HOLD(승인했지만 안전장치·보류로 실행되지 않음, basis에 근거) / EXECUTE(실행, 기관거래고유번호·금액) / "
					+ "FAIL(금융망 거부, 코드·사유) / CANCEL(출금일 경과·부족액 해소). 오래된 것부터 정렬. "
					+ "실패 후 되살아난 제안은 행에 실패 흔적이 없으므로 이전 시도는 history의 FAIL로 확인합니다.",
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
									name = "한도 차단 후 실행된 건",
									value = "{\"success\":true,\"code\":\"SUCCESS\",\"message\":\"요청이 성공했습니다.\",\"data\":{\"transfer\":{\"id\":21,\"status\":\"EXECUTED\",\"scheduledDate\":\"2026-09-14\",\"dueDate\":\"2026-09-15\",\"requiredAmount\":230000,\"fromAccountId\":1,\"toAccountId\":3,\"purpose\":{\"type\":\"FIXED\",\"fixedExpenseId\":7,\"cardBillingId\":null,\"name\":\"월세\"},\"executedAt\":\"2026-09-14T09:12:00\",\"failReason\":null,\"createdAt\":\"2026-09-14T08:30:12\"},\"history\":[{\"action\":\"HOLD\",\"basis\":\"PAY_009 1일 이체 한도를 초과합니다. — 오늘 실행 600000 + 금액 230000 > 1일 한도 800000\",\"at\":\"2026-09-14T08:41:03\"},{\"action\":\"EXECUTE\",\"basis\":\"금융망 H0000 — 기관거래고유번호 20260914091200000012, 금액 230000, 계좌 1→3\",\"at\":\"2026-09-14T09:12:00\"}]}}"
							)
					)
			),
			@ApiResponse(responseCode = "404", description = "본인 소유가 아니거나 없는 제안(PAY_005)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "401", description = "Access Token이 없거나 유효하지 않음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	})
	BaseResponse<TransferDetailResponse> detail(Long userId, long transferId);

	@Operation(
			summary = "이체 승인·실행",
			description = "PROPOSED 제안을 승인하면 안전장치 4검사(사전 동의 → 1회 한도 → 1일 누적 한도 → 출금 계좌가 수입·관리 계좌) 후 "
					+ "기관거래고유번호를 채번해 APPROVED로 기록하고 금융망 이체를 호출합니다. 성공 시 EXECUTED, 금융망 거부 시 FAILED로 기록되며 "
					+ "모든 결과는 감사 로그(EXECUTE/HOLD/FAIL)에 남습니다. 한도가 미설정(null)인 사용자는 해당 검사를 건너뜁니다. "
					+ "APPROVED로 남은 건(응답 유실)을 다시 승인하면 검사 없이 같은 번호로 재시도하고, 금융망이 H1007(중복)이면 이미 성공한 것으로 EXECUTED 처리합니다.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(
					responseCode = "200",
					description = "실행 완료",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = @ExampleObject(
									name = "실행 완료",
									value = "{\"success\":true,\"code\":\"SUCCESS\",\"message\":\"요청이 성공했습니다.\",\"data\":{\"id\":21,\"status\":\"EXECUTED\",\"executedAt\":\"2026-09-14T09:12:00\",\"failReason\":null}}"
							)
					)
			),
			@ApiResponse(responseCode = "401", description = "Access Token이 없거나 유효하지 않음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "403", description = "안전장치 차단 — 사전 동의 꺼짐(PAY_007) / 1회 한도 초과(PAY_008) / 1일 한도 초과(PAY_009) / 출금 계좌 부적격(PAY_010). 이체 미실행, HOLD 감사 기록",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "404", description = "본인의 제안이 아니거나 없음(PAY_005)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "409", description = "승인 대기·실행 중 상태가 아님(PAY_006) — 이미 실행·실패·취소된 제안",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "422", description = "금융망 거부 — 출금 계좌 잔액 부족(PAY_011, A1014) / 은행 이체 한도 초과(PAY_012, A1016·A1017). 상태 FAILED로 기록",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "503", description = "금융망 일시 장애(FINANCE_004) — 제안은 APPROVED로 남으며 다시 승인하면 같은 번호로 재시도",
					content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	})
	BaseResponse<TransferApproveResponse> approve(Long userId, long transferId);

	@Operation(
			summary = "이체 제안 보류(나중에)",
			description = "제안 상태(PROPOSED)는 바꾸지 않고 사용자가 보류했다는 감사 로그(HOLD)만 남깁니다. 캘린더·목록에서 언제든 다시 승인할 수 있으며, "
					+ "출금일이 지나면 배치가 CANCELED로 정리합니다.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(
					responseCode = "200",
					description = "보류 기록 완료",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = @ExampleObject(name = "보류", value = "{\"success\":true,\"code\":\"SUCCESS\",\"message\":\"요청이 성공했습니다.\",\"data\":null}")
					)
			),
			@ApiResponse(responseCode = "401", description = "Access Token이 없거나 유효하지 않음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "404", description = "본인의 제안이 아니거나 없음(PAY_005)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "409", description = "승인 대기 상태가 아님(PAY_006)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	})
	BaseResponse<Void> postpone(Long userId, long transferId);
}
