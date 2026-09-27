package com.finset.key_fin.budget.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;
import java.util.List;
import java.util.Optional;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.test.util.ReflectionTestUtils;

import com.finset.key_fin.budget.entity.Budget;
import com.finset.key_fin.budget.entity.BudgetAlertLevel;
import com.finset.key_fin.budget.entity.BudgetAlertState;
import com.finset.key_fin.budget.event.BudgetAlertCreated;
import com.finset.key_fin.budget.repository.BudgetAlertStateRepository;
import com.finset.key_fin.budget.repository.BudgetRepository;
import com.finset.key_fin.budget.service.EnvelopeBalanceService.EnvelopeBalance;
import com.finset.key_fin.notification.entity.NotificationType;
import com.finset.key_fin.notification.service.NotificationService;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.repository.UserSettingsRepository;

class BudgetNotificationServiceTest {

	private static final long USER_ID = 1L;
	private static final long BUDGET_ID = 900L;
	private static final int ENVELOPE_ID = 1;
	private static final String MONTH = "202609";

	private final BudgetRepository budgetRepository = mock(BudgetRepository.class);
	private final BudgetAlertStateRepository alertStateRepository = mock(BudgetAlertStateRepository.class);
	private final UserSettingsRepository userSettingsRepository = mock(UserSettingsRepository.class);
	private final EnvelopeBalanceService envelopeBalanceService = mock(EnvelopeBalanceService.class);
	private final NotificationService notifications = mock(NotificationService.class);
	private final ApplicationEventPublisher events = mock(ApplicationEventPublisher.class);

	private BudgetNotificationService service;

	@BeforeEach
	void setUp() {
		service = new BudgetNotificationService(budgetRepository, alertStateRepository,
				userSettingsRepository, envelopeBalanceService, notifications, events,
				Clock.fixed(Instant.parse("2026-09-10T03:00:00Z"), ZoneId.of("Asia/Seoul")));
		given(userSettingsRepository.findById(USER_ID)).willReturn(Optional.empty());
		given(budgetRepository.findByUserIdAndBudgetMonth(USER_ID, MONTH)).willReturn(Optional.of(budget()));
	}

	@Test
	void 처음_구간에_들어가면_알림을_만들고_상태를_저장한다() {
		balance(100_000L, 80_000L);
		given(alertStateRepository.findByBudgetIdAndEnvelopeId(BUDGET_ID, ENVELOPE_ID))
				.willReturn(Optional.empty());

		service.evaluate(USER_ID, ENVELOPE_ID, null);

		verify(alertStateRepository).save(any(BudgetAlertState.class));
		verify(notifications).create(eq(USER_ID), eq(NotificationType.BUDGET_ALERT),
				eq("외식 봉투가 20% 남았어요"), eq("남은 금액 20,000원"), eq("1"), eq(false));
	}

	@Test
	void 한_거래로_구간을_건너뛰어도_알림은_한_건이다() {
		balance(100_000L, 92_000L);
		given(alertStateRepository.findByBudgetIdAndEnvelopeId(BUDGET_ID, ENVELOPE_ID))
				.willReturn(Optional.empty());

		service.evaluate(USER_ID, ENVELOPE_ID, null);

		verify(notifications).create(eq(USER_ID), eq(NotificationType.BUDGET_ALERT),
				eq("외식 봉투가 8% 남았어요"), eq("남은 금액 8,000원"), eq("1"), eq(false));
	}

	@Test
	void 같은_단계면_다시_알리지_않는다() {
		balance(100_000L, 85_000L);
		given(alertStateRepository.findByBudgetIdAndEnvelopeId(BUDGET_ID, ENVELOPE_ID))
				.willReturn(Optional.of(state(BudgetAlertLevel.REMAINING_20)));

		service.evaluate(USER_ID, ENVELOPE_ID, null);

		verify(notifications, never()).create(anyLong(), any(), anyString(), anyString(), any(), anyBoolean());
	}

	@Test
	void 회복하면_알림_없이_단계만_낮춘다() {
		balance(100_000L, 60_000L);
		BudgetAlertState state = state(BudgetAlertLevel.REMAINING_5);
		given(alertStateRepository.findByBudgetIdAndEnvelopeId(BUDGET_ID, ENVELOPE_ID))
				.willReturn(Optional.of(state));

		service.evaluate(USER_ID, ENVELOPE_ID, null);

		assertThat(state.getLastAlertLevel()).isEqualTo(BudgetAlertLevel.REMAINING_50);
		verify(notifications, never()).create(anyLong(), any(), anyString(), anyString(), any(), anyBoolean());
	}

	@Test
	void 회복_뒤_다시_나빠지면_알린다() {
		balance(100_000L, 96_000L);
		BudgetAlertState state = state(BudgetAlertLevel.REMAINING_50);
		given(alertStateRepository.findByBudgetIdAndEnvelopeId(BUDGET_ID, ENVELOPE_ID))
				.willReturn(Optional.of(state));

		service.evaluate(USER_ID, ENVELOPE_ID, null);

		assertThat(state.getLastAlertLevel()).isEqualTo(BudgetAlertLevel.REMAINING_5);
		verify(notifications).create(eq(USER_ID), eq(NotificationType.BUDGET_ALERT),
				eq("외식 봉투가 4% 남았어요"), eq("남은 금액 4,000원"), eq("1"), eq(false));
	}

	@Test
	void 초과는_제목에_상태만_본문에_초과액을_담고_행동을_요구한다() {
		balance(100_000L, 112_000L);
		given(alertStateRepository.findByBudgetIdAndEnvelopeId(BUDGET_ID, ENVELOPE_ID))
				.willReturn(Optional.of(state(BudgetAlertLevel.REMAINING_5)));

		service.evaluate(USER_ID, ENVELOPE_ID, null);

		verify(notifications).create(eq(USER_ID), eq(NotificationType.BUDGET_ALERT),
				eq("외식 봉투를 초과했어요"), eq("12,000원 초과했어요"), eq("1"), eq(true));
	}

	@Test
	void 확정액이_없는_봉투는_대상이_아니다() {
		given(envelopeBalanceService.getMonthlyBalances(USER_ID, MONTH))
				.willReturn(List.of(new EnvelopeBalance(ENVELOPE_ID, "외식", null, 50_000L)));

		service.evaluate(USER_ID, ENVELOPE_ID, null);

		verify(notifications, never()).create(anyLong(), any(), anyString(), anyString(), any(), anyBoolean());
	}

	@Test
	void 소비가_적어_NONE이면_상태를_만들지_않는다() {
		balance(100_000L, 10_000L);
		given(alertStateRepository.findByBudgetIdAndEnvelopeId(BUDGET_ID, ENVELOPE_ID))
				.willReturn(Optional.empty());

		service.evaluate(USER_ID, ENVELOPE_ID, null);

		verify(alertStateRepository, never()).save(any());
		verify(notifications, never()).create(anyLong(), any(), anyString(), anyString(), any(), anyBoolean());
	}

	@Test
	void 현재_주기_예산이_없으면_평가하지_않는다() {
		given(budgetRepository.findByUserIdAndBudgetMonth(USER_ID, MONTH)).willReturn(Optional.empty());

		service.evaluate(USER_ID, ENVELOPE_ID, null);

		verify(notifications, never()).create(anyLong(), any(), anyString(), anyString(), any(), anyBoolean());
	}

	@Test
	void 취소로_단계가_좋아지면_복구_알림을_보낸다() {
		balance(100_000L, 60_000L);
		BudgetAlertState state = state(BudgetAlertLevel.EXCEEDED);
		given(alertStateRepository.findByBudgetIdAndEnvelopeId(BUDGET_ID, ENVELOPE_ID))
				.willReturn(Optional.of(state));

		service.evaluate(USER_ID, ENVELOPE_ID, 12_000L);

		assertThat(state.getLastAlertLevel()).isEqualTo(BudgetAlertLevel.REMAINING_50);
		verify(notifications).create(eq(USER_ID), eq(NotificationType.BUDGET_ALERT),
				eq("결제가 취소돼 외식 봉투가 돌아왔어요"), eq("12,000원이 복구돼 남은 금액 40,000원이에요"),
				eq("1"), eq(false));
	}

	@Test
	void 취소여도_단계가_그대로면_알리지_않는다() {
		balance(100_000L, 60_000L);
		BudgetAlertState state = state(BudgetAlertLevel.REMAINING_50);
		given(alertStateRepository.findByBudgetIdAndEnvelopeId(BUDGET_ID, ENVELOPE_ID))
				.willReturn(Optional.of(state));

		service.evaluate(USER_ID, ENVELOPE_ID, 3_000L);

		assertThat(state.getLastAlertLevel()).isEqualTo(BudgetAlertLevel.REMAINING_50);
		verify(notifications, never()).create(anyLong(), any(), anyString(), anyString(), any(), anyBoolean());
	}

	@Test
	void 구간이_나빠져_알림을_만들면_알림_id와_함께_BudgetAlertCreated를_발행한다() {
		balance(100_000L, 82_000L);
		given(alertStateRepository.findByBudgetIdAndEnvelopeId(BUDGET_ID, ENVELOPE_ID))
				.willReturn(Optional.of(state(BudgetAlertLevel.REMAINING_50)));
		given(notifications.create(anyLong(), any(), anyString(), anyString(), any(), anyBoolean())).willReturn(77L);

		service.evaluate(USER_ID, ENVELOPE_ID, null);

		verify(events).publishEvent(new BudgetAlertCreated(USER_ID, ENVELOPE_ID, "외식", 77L, BudgetAlertLevel.REMAINING_20));
	}

	@Test
	void 취소_복구_알림에는_BudgetAlertCreated를_발행하지_않는다() {
		balance(100_000L, 60_000L);
		given(alertStateRepository.findByBudgetIdAndEnvelopeId(BUDGET_ID, ENVELOPE_ID))
				.willReturn(Optional.of(state(BudgetAlertLevel.EXCEEDED)));

		service.evaluate(USER_ID, ENVELOPE_ID, 12_000L);

		verify(events, never()).publishEvent(any(BudgetAlertCreated.class));
	}

	private void balance(long confirmed, long spent) {
		given(envelopeBalanceService.getMonthlyBalances(USER_ID, MONTH))
				.willReturn(List.of(new EnvelopeBalance(ENVELOPE_ID, "외식", confirmed, spent)));
	}

	private Budget budget() {
		Budget budget = Budget.propose(User.create("keyfin-tester@example.com", "password", "정재원"), MONTH);
		ReflectionTestUtils.setField(budget, "id", BUDGET_ID);
		return budget;
	}

	private BudgetAlertState state(BudgetAlertLevel level) {
		return BudgetAlertState.start(BUDGET_ID, ENVELOPE_ID, level);
	}
}
