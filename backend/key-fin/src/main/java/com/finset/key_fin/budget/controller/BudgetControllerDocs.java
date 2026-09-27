package com.finset.key_fin.budget.controller;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

import com.finset.key_fin.budget.dto.request.BudgetConfirmRequest;
import com.finset.key_fin.budget.dto.request.EmergencyFundRequest;
import com.finset.key_fin.budget.dto.response.BudgetConfirmResponse;
import com.finset.key_fin.budget.dto.response.BudgetCurrentResponse;
import com.finset.key_fin.budget.dto.response.EmergencyFundResponse;
import com.finset.key_fin.budget.dto.response.BudgetProposalResponse;
import com.finset.key_fin.global.base.BaseResponse;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.ExampleObject;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;

@Tag(
		name = "예산",
		description = "카테고리(봉투)별 예산 제안·승인·조회를 제공합니다."
)
public interface BudgetControllerDocs {

	@Operation(
			summary = "예산 제안 생성",
			description = "요청 시점과 사용자의 예산 기준일로 현재 주기를 정해, 직전 3개월 순소비를 커버 일수 비례 월평균으로 환산한 "
					+ "봉투 7종의 예산을 제안합니다. 요청 바디 없음. 이력이 없으면 기본 템플릿으로 제안하며, "
					+ "현재 주기의 예산이 이미 있으면 409를 반환합니다.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(
					responseCode = "200",
					description = "예산 제안 생성 성공",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = @ExampleObject(
									name = "제안 생성 성공",
									value = "{\"success\":true,\"code\":\"SUCCESS\",\"message\":\"요청이 성공했습니다.\",\"data\":{\"budgetId\":11,\"month\":\"202609\",\"status\":\"PROPOSED\",\"basis\":\"최근 3개월 평균 (2026-06-02~2026-09-01)\",\"envelopes\":[{\"envelopeId\":1,\"name\":\"외식\",\"proposedAmount\":121000,\"monthlyAvg\":120652}]}}"
							)
					)
			),
			@ApiResponse(
					responseCode = "401",
					description = "Access Token이 없거나 유효하지 않음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "409",
					description = "해당 주기의 예산이 이미 존재",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "500",
					description = "서버 내부 오류",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			)
	})
	BaseResponse<BudgetProposalResponse> propose(Long userId);

	@Operation(
			summary = "현재 주기 예산·잔액 조회 (보드)",
			description = "요청 시점과 사용자 기준일로 정한 현재 주기의 예산을 반환합니다. "
					+ "예산이 없으면 제안을 생성해 PROPOSED로 응답합니다. "
					+ "PROPOSED면 봉투별 제안액만(확정 화면 복원용), CONFIRMED면 전체·봉투별 확정액·소비·잔액·잔여율을 반환합니다. "
					+ "remainingRate는 정수 내림, 초과 시 음수, 확정액 0인 봉투는 null. "
					+ "periodFrom~periodTo는 주기의 시작일과 마지막 날(포함) — month는 주기 시작일이 속한 월 라벨이라 달력 월과 다를 수 있음.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(
					responseCode = "200",
					description = "조회 성공",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = {
									@ExampleObject(
											name = "확정된 예산",
											value = "{\"success\":true,\"code\":\"SUCCESS\",\"message\":\"요청이 성공했습니다.\",\"data\":{\"budgetId\":11,\"month\":\"202609\",\"periodFrom\":\"2026-09-01\",\"periodTo\":\"2026-09-30\",\"status\":\"CONFIRMED\",\"total\":{\"confirmed\":780000,\"spent\":298000,\"remaining\":482000,\"remainingRate\":61},\"envelopes\":[{\"envelopeId\":1,\"name\":\"외식\",\"proposedAmount\":null,\"confirmedAmount\":280000,\"spent\":148000,\"remaining\":132000,\"remainingRate\":47},{\"envelopeId\":3,\"name\":\"의료·건강\",\"proposedAmount\":null,\"confirmedAmount\":0,\"spent\":30000,\"remaining\":-30000,\"remainingRate\":null}]}}"
									),
									@ExampleObject(
											name = "미확정(제안) 예산",
											value = "{\"success\":true,\"code\":\"SUCCESS\",\"message\":\"요청이 성공했습니다.\",\"data\":{\"budgetId\":12,\"month\":\"202608\",\"periodFrom\":\"2026-08-23\",\"periodTo\":\"2026-09-22\",\"status\":\"PROPOSED\",\"total\":null,\"envelopes\":[{\"envelopeId\":1,\"name\":\"외식\",\"proposedAmount\":300000,\"confirmedAmount\":null,\"spent\":null,\"remaining\":null,\"remainingRate\":null}]}}"
									)
							}
					)
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
	BaseResponse<BudgetCurrentResponse> getCurrent(Long userId);

	@Operation(
			summary = "예산 승인·조정",
			description = "제안(PROPOSED) 상태인 예산의 봉투 7종 전부에 확정 금액을 기록하고 CONFIRMED로 전환합니다. "
					+ "금액은 0 이상 1,000원 단위. 제안액(proposedAmount)은 보존됩니다. "
					+ "확정은 주기당 1회 — 이미 CONFIRMED면 409를 반환합니다.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(
					responseCode = "200",
					description = "예산 확정 성공",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = @ExampleObject(
									name = "확정 성공",
									value = "{\"success\":true,\"code\":\"SUCCESS\",\"message\":\"요청이 성공했습니다.\",\"data\":{\"budgetId\":11,\"month\":\"202609\",\"status\":\"CONFIRMED\"}}"
							)
					)
			),
			@ApiResponse(
					responseCode = "400",
					description = "봉투 목록이 예산 구성과 불일치, 금액이 음수 또는 1,000원 단위 아님",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "401",
					description = "Access Token이 없거나 유효하지 않음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "404",
					description = "본인 소유의 예산이 아니거나 존재하지 않음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "409",
					description = "이미 확정된 예산",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "500",
					description = "서버 내부 오류",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			)
	})
	BaseResponse<BudgetConfirmResponse> confirm(Long userId, Long budgetId, BudgetConfirmRequest request);

	@Operation(
			summary = "비상금 설정",
			description = "현재 예산(budgetId는 GET /budgets/current의 값)의 비상금 월 금액을 설정합니다. 비상금은 실제 계좌가 아닌 가상 풀이며, "
					+ "사용액(spent)은 주기 내 EMERGENCY 태그 거래의 합, 잔액(remaining)은 설정액 − 사용액(음수 가능)입니다. "
					+ "금액은 0 이상 1,000원 단위, 0이면 해제(미설정과 같은 상태). 예산 확정 여부와 무관하게 주기 중 언제든 바꿀 수 있고, "
					+ "이체·예산 제안·봉투 잔액에는 영향을 주지 않습니다. 같은 값이 GET /budgets/current의 emergency 객체로도 조회됩니다.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(
					responseCode = "200",
					description = "설정 성공",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = @ExampleObject(
									name = "설정 성공",
									value = "{\"success\":true,\"code\":\"SUCCESS\",\"message\":\"요청이 성공했습니다.\",\"data\":{\"budgetId\":11,\"emergency\":{\"amount\":200000,\"spent\":45000,\"remaining\":155000}}}"
							)
					)
			),
			@ApiResponse(responseCode = "400", description = "금액이 없거나 음수(COMMON_001) 또는 1,000원 단위 아님(BUDGET_005)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "401", description = "Access Token이 없거나 유효하지 않음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "404", description = "본인 소유의 예산이 아니거나 존재하지 않음(BUDGET_002)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	})
	BaseResponse<EmergencyFundResponse> updateEmergency(Long userId, Long budgetId, EmergencyFundRequest request);
}
