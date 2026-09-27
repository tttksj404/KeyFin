package com.finset.key_fin.payment.controller;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

import java.util.List;

import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.payment.dto.request.FixedExpenseCardRequest;
import com.finset.key_fin.payment.dto.request.FixedExpenseRequest;
import com.finset.key_fin.payment.dto.response.FixedExpenseIdResponse;
import com.finset.key_fin.payment.dto.response.FixedExpenseResponse;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.ExampleObject;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;

@Tag(
		name = "고정지출",
		description = "금융망에 없는 정기 지출(월세·공과금 등)을 직접 등록·관리합니다. 금융망 정기결제는 동기화로 들어오며 여기서는 조회만 됩니다."
)
public interface FixedExpenseControllerDocs {

	@Operation(
			summary = "고정지출 등록",
			description = "월세·구독·공과금·대출 상환 등 매월 나가는 지출을 직접 등록합니다. CARD_BILL은 청구서로 자동 계산되므로 등록할 수 없습니다. "
					+ "금액은 1원 이상(변동형은 예상액 필수), 출금일 1~31(없는 날짜는 해당 월 말일로 보정), 출금 계좌는 본인의 관리 대상 계좌. "
					+ "활성 항목과 이름·유형·금액·출금일·계좌가 모두 같으면 409.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(
					responseCode = "201",
					description = "등록 성공",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = @ExampleObject(
									name = "등록 성공",
									value = "{\"success\":true,\"code\":\"SUCCESS\",\"message\":\"요청이 성공했습니다.\",\"data\":{\"id\":7}}"
							)
					)
			),
			@ApiResponse(
					responseCode = "400",
					description = "입력값 오류(COMMON_001) 또는 CARD_BILL 직접 등록(PAY_004)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "401",
					description = "Access Token이 없거나 유효하지 않음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "404",
					description = "출금 계좌가 본인 소유가 아니거나 없음(ACCOUNT_001)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "409",
					description = "같은 내용의 고정지출이 이미 있음(PAY_003) 또는 관리 대상이 아닌 계좌(ACCOUNT_002)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "500",
					description = "서버 내부 오류",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			)
	})
	BaseResponse<FixedExpenseIdResponse> register(Long userId, FixedExpenseRequest request);

	@Operation(
			summary = "고정지출 목록",
			description = "본인의 활성 고정지출을 등록 순으로 반환합니다. 금융망에서 동기화된 정기결제도 포함되며 synced=true로 표시됩니다 — "
					+ "이 항목은 수정·삭제할 수 없으므로 화면에서 버튼을 잠가 주세요.",
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
									name = "목록",
									value = "{\"success\":true,\"code\":\"SUCCESS\",\"message\":\"요청이 성공했습니다.\",\"data\":[{\"id\":7,\"name\":\"월세\",\"expenseType\":\"RENT\",\"amount\":550000,\"isVariable\":false,\"paymentDay\":15,\"withdrawalAccountId\":3,\"synced\":false},{\"id\":8,\"name\":\"FLO 개인\",\"expenseType\":\"SUBSCRIPTION\",\"amount\":7900,\"isVariable\":false,\"paymentDay\":15,\"withdrawalAccountId\":3,\"synced\":true}]}"
							)
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
	BaseResponse<List<FixedExpenseResponse>> list(Long userId);

	@Operation(
			summary = "고정지출 수정",
			description = "요청 바디 전체로 교체합니다(부분 수정 없음). 검증 규칙은 등록과 동일. "
					+ "금융망에서 동기화된 항목은 수정할 수 없습니다 — 카드사·서비스에서 변경하면 다음 동기화에 반영됩니다.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(
					responseCode = "200",
					description = "수정 성공",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = @ExampleObject(
									name = "수정 성공",
									value = "{\"success\":true,\"code\":\"SUCCESS\",\"message\":\"요청이 성공했습니다.\",\"data\":{\"id\":7}}"
							)
					)
			),
			@ApiResponse(
					responseCode = "400",
					description = "입력값 오류(COMMON_001) 또는 CARD_BILL(PAY_004)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "401",
					description = "Access Token이 없거나 유효하지 않음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "404",
					description = "고정지출이 본인 소유가 아니거나 없거나 삭제됨(PAY_001), 출금 계좌 없음(ACCOUNT_001)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "409",
					description = "금융망 동기화 항목(PAY_002) 또는 관리 대상이 아닌 계좌(ACCOUNT_002)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "500",
					description = "서버 내부 오류",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			)
	})
	BaseResponse<FixedExpenseIdResponse> update(Long userId, long fixedExpenseId, FixedExpenseRequest request);

	@Operation(
			summary = "카드 정기결제 결제 카드 지정",
			description = "금융망 정기결제 조회에는 결제 카드가 없어, 관리 카드가 2장 이상이면 새 구독마다 사용자가 한 번 지정합니다"
					+ "(SUBSCRIPTION_CARD 알림, refId=고정지출 ID). 지정한 카드는 AI 코칭 예측에 반영됩니다. "
					+ "금융망 동기화 항목만 대상이며, 다시 호출하면 카드를 바꿉니다.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(
					responseCode = "200",
					description = "지정 성공",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = @ExampleObject(
									name = "지정 성공",
									value = "{\"success\":true,\"code\":\"SUCCESS\",\"message\":\"요청이 성공했습니다.\",\"data\":{\"id\":8}}"
							)
					)
			),
			@ApiResponse(
					responseCode = "400",
					description = "입력값 오류(COMMON_001)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "401",
					description = "Access Token이 없거나 유효하지 않음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "404",
					description = "고정지출이 본인 소유가 아니거나 없거나 삭제됨(PAY_001), 카드가 본인 소유가 아니거나 없음(PAY_013)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "409",
					description = "금융망 정기결제가 아닌 항목(PAY_014) 또는 관리 대상이 아닌 카드(PAY_015)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "500",
					description = "서버 내부 오류",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			)
	})
	BaseResponse<FixedExpenseIdResponse> assignCard(Long userId, long fixedExpenseId, FixedExpenseCardRequest request);

	@Operation(
			summary = "고정지출 삭제",
			description = "앞으로의 일정에서 제외합니다(내부적으로 비활성화 — 이미 만들어진 이체 기록은 보존). "
					+ "금융망에서 동기화된 항목은 삭제할 수 없습니다.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(
					responseCode = "200",
					description = "삭제 성공",
					content = @Content(
							mediaType = APPLICATION_JSON_VALUE,
							schema = @Schema(implementation = BaseResponse.class),
							examples = @ExampleObject(
									name = "삭제 성공",
									value = "{\"success\":true,\"code\":\"SUCCESS\",\"message\":\"요청이 성공했습니다.\",\"data\":null}"
							)
					)
			),
			@ApiResponse(
					responseCode = "401",
					description = "Access Token이 없거나 유효하지 않음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "404",
					description = "고정지출이 본인 소유가 아니거나 없거나 이미 삭제됨(PAY_001)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "409",
					description = "금융망 동기화 항목(PAY_002)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			),
			@ApiResponse(
					responseCode = "500",
					description = "서버 내부 오류",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))
			)
	})
	BaseResponse<Void> delete(Long userId, long fixedExpenseId);
}
