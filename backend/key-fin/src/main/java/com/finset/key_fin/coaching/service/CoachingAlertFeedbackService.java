package com.finset.key_fin.coaching.service;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Service;

import com.finset.key_fin.budget.entity.BudgetAlertLevel;
import com.finset.key_fin.budget.event.BudgetAlertCreated;
import com.finset.key_fin.coaching.client.CoachingEnvelopeReviewClient;
import com.finset.key_fin.coaching.client.CoachingTwinClient;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Slf4j
@Service
@RequiredArgsConstructor
@ConditionalOnProperty(prefix = "coaching.api", name = "token")
public class CoachingAlertFeedbackService {

	private final CoachingTwinClient twinClient;
	private final FdtBootstrapService bootstrapService;
	private final CoachingEnvelopeReviewClient reviewClient;
	private final CoachingAlertFeedbackStore store;

	/** 트윈이 거부되면 평가하지 않는다. 이전 트윈에는 알림을 일으킨 결제가 없다. */
	public void generate(BudgetAlertCreated alert) {
		try {
			twinClient.create(alert.userId(), bootstrapService.build(alert.userId()));
		} catch (RuntimeException e) {
			log.warn("코치 피드백 생략 — 트윈 전송 실패: userId={}, notificationId={}, cause={}",
					alert.userId(), alert.notificationId(), e.toString());
			store.failed(alert.userId(), alert.notificationId());
			return;
		}
		try {
			String text = reviewClient.review(alert.userId(), alert.envelopeName(), tier(alert.level()),
					"alert-feedback-" + alert.notificationId()).text();
			if (text == null || text.isBlank()) {
				store.failed(alert.userId(), alert.notificationId());
				return;
			}
			store.ready(alert.userId(), alert.notificationId(), text);
		} catch (RuntimeException e) {
			log.warn("코치 피드백 실패: userId={}, notificationId={}, cause={}",
					alert.userId(), alert.notificationId(), e.toString());
			store.failed(alert.userId(), alert.notificationId());
		}
	}

	static String tier(BudgetAlertLevel level) {
		return switch (level) {
			case REMAINING_50 -> "50";
			case REMAINING_20 -> "20";
			case REMAINING_5 -> "5";
			case EXCEEDED -> "over";
			case NONE -> throw new IllegalArgumentException("NONE 단계는 알림 대상이 아니다");
		};
	}
}
