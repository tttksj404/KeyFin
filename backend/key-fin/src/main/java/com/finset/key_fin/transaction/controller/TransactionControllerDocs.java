package com.finset.key_fin.transaction.controller;

import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.transaction.dto.request.TransactionClassificationRequest;
import com.finset.key_fin.transaction.dto.request.TransactionMemoUpdateRequest;
import com.finset.key_fin.transaction.dto.request.BulkTransactionClassificationRequest;
import com.finset.key_fin.transaction.dto.response.BulkTransactionClassificationResponse;
import com.finset.key_fin.transaction.dto.response.TransactionClassificationResponse;
import com.finset.key_fin.transaction.dto.response.TransactionListResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.ExampleObject;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;

import static org.springframework.http.MediaType.APPLICATION_JSON_VALUE;

@Tag(name = "거래", description = "거래 내역 조회 및 분류 API입니다. Access Token이 필요합니다.")
public interface TransactionControllerDocs {

	@Operation(
			summary = "거래 내역 조회",
			description = "현재 사용자의 거래를 거래일자·거래시각 최신순으로 조회합니다. 월을 생략하면 현재 월을 사용하며, "
					+ "취소 거래와 예산 제외 거래도 포함합니다.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(responseCode = "200", description = "거래 내역 조회 성공", useReturnTypeSchema = true,
					content = @Content(mediaType = APPLICATION_JSON_VALUE,
							examples = @ExampleObject(value = """
									{"success":true,"code":"SUCCESS","message":"요청이 성공했습니다.","data":{"items":[{"id":501,"txType":"CARD","merchantName":"메가커피 역삼점","amount":4500,"txDate":"2026-09-08","txTime":"14:21:00","envelopeId":1,"subcategoryId":102,"subcategoryName":"카페","confirmStatus":"AUTO","excludeTag":"NONE","status":"NORMAL","memo":null,"accountId":null,"cardId":7,"adjustedAmount":null}],"nextCursor":481}}
									"""))),
			@ApiResponse(responseCode = "400", description = "월, 페이지 크기 또는 필터가 올바르지 않음 (TRANSACTION_001~003)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "401", description = "Access Token이 없거나 유효하지 않거나 만료됨",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "403", description = "접근 권한 없음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "404", description = "활성 사용자를 찾을 수 없음 (USER_001)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "500", description = "서버 내부 오류",
					content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	})
	BaseResponse<TransactionListResponse> getTransactions(
			@Parameter(hidden = true) Long userId,
			@Parameter(description = "조회 월(yyyyMM). 선택값이며 생략 시 현재 월", example = "202609") String month,
			@Parameter(description = "봉투 ID. 선택값이며 생략 시 전체 봉투 조회", example = "1") Integer envelopeId,
			@Parameter(description = "세분류 ID. 선택값이며 생략 시 전체 세분류 조회", example = "102") Integer subcategoryId,
			@Parameter(description = "계좌 ID. 선택값이며 생략 시 전체 계좌 조회", example = "3") Long accountId,
			@Parameter(description = "카드 ID. 선택값이며 생략 시 전체 카드 조회", example = "7") Long cardId,
			@Parameter(description = "이전 응답의 nextCursor. 선택값이며 첫 조회 시 생략", example = "481") Long cursor,
			@Parameter(description = "조회 개수(1~100). 선택값이며 생략 시 20", example = "20") Integer size
	);

	@Operation(
			summary = "미확정 거래 목록 조회",
			description = "현재 사용자의 전체 기간 거래 중 분류가 미확정된 정상 출금 거래를 최신순으로 조회합니다.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(responseCode = "200", description = "미확정 거래 목록 조회 성공", useReturnTypeSchema = true,
					content = @Content(mediaType = APPLICATION_JSON_VALUE,
							examples = @ExampleObject(value = """
									{"success":true,"code":"SUCCESS","message":"요청이 성공했습니다.","data":{"items":[{"id":501,"txType":"CARD","merchantName":"메가커피 역삼점","amount":4500,"txDate":"2026-09-08","txTime":"14:21:00","envelopeId":null,"subcategoryId":null,"subcategoryName":null,"confirmStatus":"PENDING","excludeTag":"NONE","status":"NORMAL","memo":null,"accountId":null,"cardId":7,"adjustedAmount":null}],"nextCursor":481}}
									"""))),
			@ApiResponse(responseCode = "400", description = "페이지 크기 또는 cursor가 올바르지 않음 (TRANSACTION_002~003)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "401", description = "Access Token이 없거나 유효하지 않거나 만료됨",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "403", description = "접근 권한 없음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "404", description = "활성 사용자를 찾을 수 없음 (USER_001)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "500", description = "서버 내부 오류",
					content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	})
	BaseResponse<TransactionListResponse> getPendingTransactions(
			@Parameter(hidden = true) Long userId,
			@Parameter(description = "이전 응답의 nextCursor", example = "481") Long cursor,
			@Parameter(description = "조회 개수(1~100, 기본 20)", example = "20") Integer size
	);

	@Operation(
			summary = "거래 분류 확정·수정",
			description = "거래를 세분류로 확정하거나 DUTCH·SELF_TRANSFER·BUDGET_EXCLUDED·EMERGENCY로 처리합니다. "
					+ "일반 지출은 subcategoryId와 excludeTag 중 하나만 입력하고, 환급 입금은 subcategoryId와 RESTORE를 함께 입력합니다. "
					+ "adjustedAmount는 DUTCH에서만 사용하며, BUDGET_EXCLUDED는 예산 계산에서 전액 제외됩니다. "
					+ "이미 확정된 거래도 수정할 수 있습니다.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(responseCode = "200", description = "거래 분류 확정·수정 성공", useReturnTypeSchema = true,
					content = @Content(mediaType = APPLICATION_JSON_VALUE,
							examples = @ExampleObject(value = """
									{"success":true,"code":"SUCCESS","message":"요청이 성공했습니다.","data":{"transactionId":501,"subcategoryId":102,"excludeTag":"NONE","adjustedAmount":null,"confirmStatus":"CONFIRMED"}}
									"""))),
			@ApiResponse(responseCode = "400", description = "분류 조합 또는 더치페이 실제 부담액이 올바르지 않음 (TRANSACTION_006, TRANSACTION_008)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "401", description = "Access Token이 없거나 유효하지 않거나 만료됨",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "403", description = "접근 권한 없음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "404", description = "거래·세분류 또는 활성 사용자를 찾을 수 없음 (TRANSACTION_004~005, USER_001)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "409", description = "일반 입금, 환급이 아닌 입금 처리 또는 취소 거래로 분류할 수 없음 (TRANSACTION_007)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "500", description = "서버 내부 오류",
					content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	})
	BaseResponse<TransactionClassificationResponse> classifyTransaction(
			@Parameter(hidden = true) Long userId,
			@Parameter(description = "거래 ID", example = "501", required = true) Long transactionId,
			TransactionClassificationRequest request
	);

	@Operation(
			summary = "거래 메모 수정",
			description = "현재 사용자의 거래에 메모를 저장합니다. 앞뒤 공백은 제거하며, 빈 문자열 또는 공백만 입력하면 기존 메모를 삭제합니다.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(responseCode = "200", description = "거래 메모 수정 성공"),
			@ApiResponse(responseCode = "400", description = "메모가 누락되었거나 255자를 초과함 (COMMON_001)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "401", description = "Access Token이 없거나 유효하지 않거나 만료됨",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "403", description = "접근 권한 없음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "404", description = "거래 또는 활성 사용자를 찾을 수 없음 (TRANSACTION_004, USER_001)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "500", description = "서버 내부 오류",
					content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	})
	ResponseEntity<Void> updateTransactionMemo(
			@Parameter(hidden = true) Long userId,
			@Parameter(description = "거래 ID", example = "501", required = true) Long transactionId,
			TransactionMemoUpdateRequest request
	);

	@Operation(
			summary = "미확정 거래 일괄 분류 확정",
			description = "정리 세션에서 여러 PENDING 거래의 세분류 또는 제외 태그를 한 번에 확정합니다. "
					+ "요청은 최대 100건이며 하나라도 실패하면 전체 요청을 롤백합니다. "
					+ "일반 소비는 subcategoryId, DUTCH는 adjustedAmount, 환급은 subcategoryId와 RESTORE를 함께 입력합니다. "
					+ "SELF_TRANSFER·BUDGET_EXCLUDED·EMERGENCY는 excludeTag만 입력합니다.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(responseCode = "200", description = "미확정 거래 일괄 분류 성공", useReturnTypeSchema = true,
					content = @Content(mediaType = APPLICATION_JSON_VALUE,
							examples = @ExampleObject(value = """
									{"success":true,"code":"SUCCESS","message":"요청이 성공했습니다.","data":{"confirmed":2,"pendingRemain":0}}
									"""))),
			@ApiResponse(responseCode = "400", description = "목록 크기, 중복 거래 ID 또는 분류 조합이 올바르지 않음 (COMMON_001, TRANSACTION_006, TRANSACTION_008)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "401", description = "Access Token이 없거나 유효하지 않거나 만료됨",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "403", description = "접근 권한 없음",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "404", description = "거래·세분류 또는 활성 사용자를 찾을 수 없음 (TRANSACTION_004~005, USER_001)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "409", description = "PENDING 상태가 아니거나 취소·입금 거래가 포함됨 (TRANSACTION_007)",
					content = @Content(schema = @Schema(implementation = BaseResponse.class))),
			@ApiResponse(responseCode = "500", description = "서버 내부 오류",
					content = @Content(schema = @Schema(implementation = BaseResponse.class)))
	})
	BaseResponse<BulkTransactionClassificationResponse> classifyPendingTransactions(
			@Parameter(hidden = true) Long userId,
			BulkTransactionClassificationRequest request
	);
}
