package com.finset.key_fin.coaching.controller;

import org.springframework.http.ResponseEntity;
import com.finset.key_fin.coaching.dto.ChatHistoryResponse;
import com.finset.key_fin.coaching.dto.ChatReply;
import com.finset.key_fin.coaching.dto.ChatRequest;
import com.finset.key_fin.global.base.BaseResponse;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;

@Tag(
		name = "코칭 대화",
		description = "코치 채팅창. 세션은 백엔드가 사용자당 하나 관리하며(24시간·질문 20회) 만료되면 새 세션으로 이어집니다. "
				+ "대화 본문은 코칭 서버가 보관하므로 24시간이 지나면 이력이 비어 있습니다."
)
public interface CoachingChatControllerDocs {

	@Operation(
			summary = "코치에게 질문",
			description = "kind = CHAT(금융 개념·소비 조회·안내) 또는 COACHING(예측·위험 코칭). "
					+ "status는 코칭 서버 값 그대로 — answered / needs_source(근거 자료 없음) / needs_data(개인 자료 부족) / "
					+ "needs_clarification(지원하지 않는 기간·필터) / out_of_scope(금융 외) / unavailable(모델 실패, fallbackReason 참고). "
					+ "source = llm / template(안내 문구) / engine(확정 원장 집계). "
					+ "예측·구매검토 답변은 chartId(예산 차트, GET /coaching/charts/{chartId}/html 로 렌더), "
					+ "소비 조회 답변은 rows[{envelope, totalKrw, count}]·totalKrw 가 함께 온다. 그 외에는 chartId null, rows 빈 배열.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(responseCode = "200", description = "답변"),
			@ApiResponse(responseCode = "400", description = "message가 비었거나 2000자 초과"),
			@ApiResponse(responseCode = "422", description = "AI_003 코칭 서버가 질문을 처리하지 못함(되묻기 대상 아닌 거절)"),
			@ApiResponse(responseCode = "503", description = "AI_001 코칭 서버 응답 없음")
	})
	BaseResponse<ChatReply> chat(Long userId, ChatRequest request);

	@Operation(
			summary = "현재 세션 대화 이력",
			description = "세션이 없거나 만료됐으면 messages는 빈 배열, expiresAt은 null.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(responseCode = "200", description = "이력"),
			@ApiResponse(responseCode = "503", description = "AI_001 코칭 서버 응답 없음")
	})
	BaseResponse<ChatHistoryResponse> history(Long userId);

	@Operation(
			summary = "예산 차트 HTML",
			description = "채팅 답변의 chartId 로 코칭 서버가 그린 차트 문서를 그대로 돌려준다(text/html, 웹뷰에 inline 로드). "
					+ "다른 사용자의 차트 id 는 404.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(responseCode = "200", description = "차트 HTML 문서", content = @Content(mediaType = "text/html")),
			@ApiResponse(responseCode = "404", description = "AI_002 차트 없음"),
			@ApiResponse(responseCode = "422", description = "AI_003 코칭 서버가 요청을 거절"),
			@ApiResponse(responseCode = "503", description = "AI_001 코칭 서버 응답 없음")
	})
	ResponseEntity<String> chartHtml(Long userId, String chartId);
}
