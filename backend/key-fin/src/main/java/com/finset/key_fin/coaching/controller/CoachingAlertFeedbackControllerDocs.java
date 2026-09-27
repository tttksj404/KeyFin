package com.finset.key_fin.coaching.controller;

import com.finset.key_fin.coaching.dto.CoachFeedbackResponse;
import com.finset.key_fin.global.base.BaseResponse;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;

@Tag(name = "코칭 대화")
public interface CoachingAlertFeedbackControllerDocs {

	@Operation(
			summary = "예산 구간 알림의 코치 피드백",
			description = "BUDGET_ALERT 구간 알림(50·20·5%·초과)을 받으면 서버가 AI에 그 봉투의 소비 평가를 요청해 24시간 보관한다. "
					+ "status = PENDING(평가 중) / READY(text 표시) / FAILED(생략) / NONE(없음·만료·다른 사용자). 항상 200.",
			security = @SecurityRequirement(name = "bearerAuth")
	)
	@ApiResponses({
			@ApiResponse(responseCode = "200", description = "피드백 상태")
	})
	BaseResponse<CoachFeedbackResponse> feedback(Long userId, long notificationId);
}
