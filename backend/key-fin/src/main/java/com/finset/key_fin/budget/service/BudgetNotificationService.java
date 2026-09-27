package com.finset.key_fin.budget.service;

import java.time.Clock;
import java.time.LocalDate;
import java.util.Optional;

import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.finset.key_fin.budget.entity.Budget;
import com.finset.key_fin.budget.entity.BudgetAlertLevel;
import com.finset.key_fin.budget.entity.BudgetAlertState;
import com.finset.key_fin.budget.event.BudgetAlertCreated;
import com.finset.key_fin.budget.repository.BudgetAlertStateRepository;
import com.finset.key_fin.budget.repository.BudgetRepository;
import com.finset.key_fin.budget.service.EnvelopeBalanceService.EnvelopeBalance;
import com.finset.key_fin.notification.entity.NotificationType;
import com.finset.key_fin.notification.service.NotificationService;
import com.finset.key_fin.user.entity.UserSettings;
import com.finset.key_fin.user.repository.UserSettingsRepository;

import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class BudgetNotificationService {

	private static final int DEFAULT_ANCHOR_DAY = 1;

	private final BudgetRepository budgetRepository;
	private final BudgetAlertStateRepository alertStateRepository;
	private final UserSettingsRepository userSettingsRepository;
	private final EnvelopeBalanceService envelopeBalanceService;
	private final NotificationService notificationService;
	private final ApplicationEventPublisher events;
	private final Clock clock;

	@Transactional
	public void evaluate(long userId, int envelopeId, Long restoredKrw) {
		String month = BudgetPeriod.current(LocalDate.now(clock), anchorDayOf(userId)).month();
		Optional<Budget> budget = budgetRepository.findByUserIdAndBudgetMonth(userId, month);
		if (budget.isEmpty()) {
			return;
		}
		EnvelopeBalance balance = envelopeBalanceService.getMonthlyBalances(userId, month).stream()
				.filter(row -> row.envelopeId() == envelopeId)
				.findFirst()
				.orElse(null);
		if (balance == null || balance.remaining() == null) {
			return;
		}
		BudgetAlertLevel current = BudgetAlertLevel.of(balance.confirmedAmount(), balance.remaining());
		if (current == null) {
			return;
		}
		apply(budget.get().getId(), envelopeId, current, balance, userId, restoredKrw);
	}

	private void apply(long budgetId, int envelopeId, BudgetAlertLevel current,
			EnvelopeBalance balance, long userId, Long restoredKrw) {
		BudgetAlertState state = alertStateRepository.findByBudgetIdAndEnvelopeId(budgetId, envelopeId)
				.orElse(null);
		if (state == null) {
			if (current == BudgetAlertLevel.NONE) {
				return;
			}
			alertStateRepository.save(BudgetAlertState.start(budgetId, envelopeId, current));
			notify(userId, envelopeId, current, balance);
			return;
		}
		if (current == state.getLastAlertLevel()) {
			return;
		}
		boolean worse = current.isWorseThan(state.getLastAlertLevel());
		state.moveTo(current);
		if (worse) {
			notify(userId, envelopeId, current, balance);
		} else if (restoredKrw != null) {
			notifyRecovery(userId, envelopeId, balance, restoredKrw);
		}
	}

	private void notify(long userId, int envelopeId, BudgetAlertLevel level, EnvelopeBalance balance) {
		long remaining = balance.remaining();
		String title = level == BudgetAlertLevel.EXCEEDED
				? "%s 봉투를 초과했어요".formatted(balance.envelopeName())
				: "%s 봉투가 %d%% 남았어요".formatted(balance.envelopeName(), rate(balance));
		String body = level == BudgetAlertLevel.EXCEEDED
				? "%,d원 초과했어요".formatted(-remaining)
				: "남은 금액 %,d원".formatted(remaining);
		long notificationId = notificationService.create(userId, NotificationType.BUDGET_ALERT, title, body,
				String.valueOf(envelopeId), level.requiresAction());
		events.publishEvent(new BudgetAlertCreated(userId, envelopeId, balance.envelopeName(), notificationId, level));
	}

	/** 결제 취소로 단계가 좋아졌을 때만 보낸다. 그 밖의 회복은 단계만 낮춘다(FR-BGT-05). */
	private void notifyRecovery(long userId, int envelopeId, EnvelopeBalance balance, long restoredKrw) {
		notificationService.create(userId, NotificationType.BUDGET_ALERT,
				"결제가 취소돼 %s 봉투가 돌아왔어요".formatted(balance.envelopeName()),
				"%,d원이 복구돼 남은 금액 %,d원이에요".formatted(restoredKrw, balance.remaining()),
				String.valueOf(envelopeId), false);
	}

	private static long rate(EnvelopeBalance balance) {
		return balance.remaining() * 100 / balance.confirmedAmount();
	}

	private int anchorDayOf(long userId) {
		return userSettingsRepository.findById(userId)
				.map(UserSettings::getBudgetAnchorDay)
				.orElse(DEFAULT_ANCHOR_DAY);
	}
}
