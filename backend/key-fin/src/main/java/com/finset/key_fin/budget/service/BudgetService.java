package com.finset.key_fin.budget.service;

import java.time.Clock;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.context.ApplicationEventPublisher;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.finset.key_fin.budget.dto.request.BudgetConfirmRequest;
import com.finset.key_fin.budget.dto.request.BudgetConfirmRequest.EnvelopeAmount;
import com.finset.key_fin.budget.dto.request.EmergencyFundRequest;
import com.finset.key_fin.budget.dto.response.BudgetConfirmResponse;
import com.finset.key_fin.budget.dto.response.BudgetCurrentResponse;
import com.finset.key_fin.budget.dto.response.BudgetCurrentResponse.Emergency;
import com.finset.key_fin.budget.dto.response.BudgetCurrentResponse.EnvelopeBoard;
import com.finset.key_fin.budget.dto.response.BudgetCurrentResponse.Total;
import com.finset.key_fin.budget.dto.response.BudgetProposalResponse;
import com.finset.key_fin.budget.dto.response.EmergencyFundResponse;
import com.finset.key_fin.budget.dto.response.BudgetProposalResponse.EnvelopeProposal;
import com.finset.key_fin.budget.entity.Budget;
import com.finset.key_fin.budget.entity.BudgetEnvelope;
import com.finset.key_fin.budget.entity.BudgetStatus;
import com.finset.key_fin.budget.exception.BudgetErrorCode;
import com.finset.key_fin.budget.event.EnvelopeSpendingChanged;
import com.finset.key_fin.budget.repository.BudgetEnvelopeRepository;
import com.finset.key_fin.budget.repository.BudgetRepository;
import com.finset.key_fin.budget.service.EnvelopeBalanceService.EnvelopeBalance;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.room.service.RoomStickerService;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.entity.UserSettings;
import com.finset.key_fin.user.repository.UserRepository;
import com.finset.key_fin.user.repository.UserSettingsRepository;

import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class BudgetService {

	private static final String EMERGENCY_SPENT_SQL = """
			SELECT COALESCE(SUM(t.amount), 0)
			FROM transactions t
			WHERE t.user_id = :userId
			  AND t.tx_date >= :fromDate AND t.tx_date < :toDate
			  AND t.status = 'NORMAL'
			  AND t.confirm_status IN ('AUTO', 'CONFIRMED')
			  AND t.exclude_tag = 'EMERGENCY'
			""";

	private static final String RECENT_SPENT_SQL = """
			SELECT e.id AS envelope_id,
			       e.name AS envelope_name,
			       COALESCE(sp.spent, 0) AS spent
			FROM envelopes e
			LEFT JOIN (
			    SELECT s.envelope_id,
			           SUM(CASE t.exclude_tag
			                   WHEN 'NONE'    THEN t.amount
			                   WHEN 'DUTCH'   THEN COALESCE(t.adjusted_amount, 0)
			                   WHEN 'RESTORE' THEN -t.amount
			                   ELSE 0 END) AS spent
			    FROM transactions t
			    JOIN subcategories s ON s.id = t.subcategory_id
			    WHERE t.user_id = :userId
			      AND t.tx_date >= :fromDate AND t.tx_date < :toDate
			      AND t.status = 'NORMAL'
			      AND t.confirm_status IN ('AUTO', 'CONFIRMED')
			    GROUP BY s.envelope_id
			) sp ON sp.envelope_id = e.id
			ORDER BY e.id
			""";

	private static final String TX_DATE_RANGE_SQL = """
			SELECT MIN(tx_date) AS first_date, MAX(tx_date) AS last_date FROM transactions
			WHERE user_id = :userId AND tx_date < :toDate
			""";

	private static final String PROPOSED_ENVELOPES_SQL = """
			SELECT be.envelope_id, e.name AS envelope_name, be.proposed_amount
			FROM budget_envelopes be
			JOIN envelopes e ON e.id = be.envelope_id
			WHERE be.budget_id = :budgetId
			ORDER BY be.envelope_id
			""";

	private static final int WINDOW_MONTHS = 3;
	private static final int MIN_COVERED_DAYS = 30;
	private static final int DAYS_PER_MONTH = 30;
	private static final int DEFAULT_ANCHOR_DAY = 1;
	private static final long AMOUNT_UNIT = 1_000L;
	private static final String BASIS_RECENT_AVERAGE = "최근 %d개월 평균 (%s~%s)";
	private static final String BASIS_DEFAULT_TEMPLATE = "기본 템플릿";
	private static final Map<Integer, Long> DEFAULT_TEMPLATE = Map.of(
			1, 600_000L,
			2, 100_000L,
			3, 100_000L,
			4, 100_000L,
			5, 100_000L,
			6, 150_000L,
			7, 100_000L);

	private final ApplicationEventPublisher events;
	private final JdbcClient jdbc;
	private final Clock clock;
	private final EnvelopeBalanceService envelopeBalanceService;
	private final BudgetRepository budgetRepository;
	private final BudgetEnvelopeRepository budgetEnvelopeRepository;
	private final UserRepository userRepository;
	private final UserSettingsRepository userSettingsRepository;
	private final RoomStickerService roomStickerService;

	@Transactional
	public BudgetProposalResponse propose(long userId) {
		LocalDate referenceDate = LocalDate.now(clock);
		String month = BudgetPeriod.current(referenceDate, anchorDayOf(userId)).month();
		if (budgetRepository.existsByUserIdAndBudgetMonth(userId, month)) {
			throw new BusinessException(BudgetErrorCode.BUDGET_ALREADY_EXISTS);
		}

		// 마지막 거래일 기준 3개월 — 시딩·늦은 연결로 최근 구간이 비어 있어도 공백만큼 평균이 깎이지 않게 한다.
		TxDateRange range = txDateRange(userId, referenceDate);
		LocalDate windowEnd = range.lastDate() == null ? referenceDate : range.lastDate().plusDays(1);
		LocalDate windowStart = windowEnd.minusMonths(WINDOW_MONTHS);
		LocalDate coveredFrom = range.firstDate() == null || range.firstDate().isBefore(windowStart)
				? windowStart : range.firstDate();
		List<EnvelopeSpent> recentSpent = jdbc.sql(RECENT_SPENT_SQL)
				.param("userId", userId)
				.param("fromDate", windowStart)
				.param("toDate", windowEnd)
				.query((rs, rowNum) -> new EnvelopeSpent(
						rs.getInt("envelope_id"),
						rs.getString("envelope_name"),
						rs.getLong("spent")))
				.list();
		boolean noHistory = recentSpent.stream().allMatch(spent -> spent.amount() == 0);
		long coveredDays = noHistory
				? MIN_COVERED_DAYS
				: Math.max(MIN_COVERED_DAYS, ChronoUnit.DAYS.between(coveredFrom, windowEnd));

		Budget budget = budgetRepository.save(
				Budget.propose(userRepository.getReferenceById(userId), month));

		List<BudgetEnvelope> rows = new ArrayList<>();
		List<EnvelopeProposal> proposals = new ArrayList<>();
		for (EnvelopeSpent spent : recentSpent) {
			long monthlyAvg = Math.max(0, spent.amount() * DAYS_PER_MONTH / coveredDays);
			long proposedAmount = noHistory
					? DEFAULT_TEMPLATE.get(spent.envelopeId())
					: roundToThousand(monthlyAvg);
			rows.add(BudgetEnvelope.propose(budget, spent.envelopeId(), proposedAmount));
			proposals.add(new EnvelopeProposal(spent.envelopeId(), spent.name(), proposedAmount, monthlyAvg));
		}
		budgetEnvelopeRepository.saveAll(rows);

		long coveredMonthsLabel = Math.max(1, Math.round(coveredDays / (double) DAYS_PER_MONTH));
		return new BudgetProposalResponse(
				budget.getId(),
				month,
				budget.getStatus().name(),
				noHistory
						? BASIS_DEFAULT_TEMPLATE
						: BASIS_RECENT_AVERAGE.formatted(coveredMonthsLabel, coveredFrom, windowEnd.minusDays(1)),
				proposals);
	}

	@Transactional
	public BudgetConfirmResponse confirm(long userId, long budgetId, BudgetConfirmRequest request) {
		userRepository.findActiveByIdForUpdate(userId)
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_NOT_FOUND));
		Budget budget = budgetRepository.findByIdAndUserId(budgetId, userId)
				.orElseThrow(() -> new BusinessException(BudgetErrorCode.BUDGET_NOT_FOUND));
		if (budget.isConfirmed()) {
			throw new BusinessException(BudgetErrorCode.BUDGET_ALREADY_CONFIRMED);
		}

		Map<Integer, Long> amounts = new HashMap<>();
		for (EnvelopeAmount envelope : request.envelopes()) {
			if (envelope.amount() % AMOUNT_UNIT != 0) {
				throw new BusinessException(BudgetErrorCode.AMOUNT_NOT_THOUSAND_UNIT);
			}
			if (amounts.put(envelope.envelopeId(), envelope.amount()) != null) {
				throw new BusinessException(BudgetErrorCode.ENVELOPE_MISMATCH);
			}
		}

		List<BudgetEnvelope> rows = budgetEnvelopeRepository.findByBudgetId(budgetId);
		boolean sameEnvelopes = rows.size() == amounts.size()
				&& rows.stream().allMatch(row -> amounts.containsKey(row.getEnvelopeId()));
		if (!sameEnvelopes) {
			throw new BusinessException(BudgetErrorCode.ENVELOPE_MISMATCH);
		}

		rows.forEach(row -> row.confirm(amounts.get(row.getEnvelopeId())));
		budget.confirm();
		roomStickerService.synchronize(userId);
		rows.forEach(row -> events.publishEvent(new EnvelopeSpendingChanged(userId, row.getEnvelopeId())));
		return new BudgetConfirmResponse(budget.getId(), budget.getBudgetMonth(), budget.getStatus().name());
	}

	@Transactional
	public BudgetCurrentResponse getCurrent(long userId) {
		BudgetPeriod period = BudgetPeriod.current(LocalDate.now(clock), anchorDayOf(userId));
		String month = period.month();
		LocalDate periodTo = period.to().minusDays(1);
		Budget budget = budgetRepository.findByUserIdAndBudgetMonth(userId, month)
				.orElseGet(() -> budgetRepository.getReferenceById(propose(userId).budgetId()));

		if (!budget.isConfirmed()) {
			List<EnvelopeBoard> envelopes = jdbc.sql(PROPOSED_ENVELOPES_SQL)
					.param("budgetId", budget.getId())
					.query((rs, rowNum) -> EnvelopeBoard.proposed(
							rs.getInt("envelope_id"),
							rs.getString("envelope_name"),
							rs.getLong("proposed_amount")))
					.list();
			return new BudgetCurrentResponse(
					budget.getId(), month, period.from(), periodTo, BudgetStatus.PROPOSED.name(), null, envelopes,
					emergencyOf(userId, budget, period));
		}

		long confirmed = 0;
		long spent = 0;
		List<EnvelopeBoard> envelopes = new ArrayList<>();
		for (EnvelopeBalance balance : envelopeBalanceService.getMonthlyBalances(userId, month)) {
			confirmed += balance.confirmedAmount();
			spent += balance.spent();
			envelopes.add(EnvelopeBoard.confirmed(
					balance.envelopeId(),
					balance.envelopeName(),
					balance.confirmedAmount(),
					balance.spent(),
					balance.remaining(),
					remainingRate(balance.remaining(), balance.confirmedAmount())));
		}
		long remaining = confirmed - spent;
		return new BudgetCurrentResponse(
				budget.getId(),
				month,
				period.from(),
				periodTo,
				BudgetStatus.CONFIRMED.name(),
				new Total(confirmed, spent, remaining, remainingRate(remaining, confirmed)),
				envelopes,
				emergencyOf(userId, budget, period));
	}

	@Transactional
	public EmergencyFundResponse updateEmergency(long userId, long budgetId, EmergencyFundRequest request) {
		Budget budget = budgetRepository.findByIdAndUserId(budgetId, userId)
				.orElseThrow(() -> new BusinessException(BudgetErrorCode.BUDGET_NOT_FOUND));
		if (request.amount() % AMOUNT_UNIT != 0) {
			throw new BusinessException(BudgetErrorCode.AMOUNT_NOT_THOUSAND_UNIT);
		}
		budget.updateEmergencyAmount(request.amount());
		BudgetPeriod period = BudgetPeriod.of(budget.getBudgetMonth(), anchorDayOf(userId));
		return new EmergencyFundResponse(budget.getId(), emergencyOf(userId, budget, period));
	}

	private Emergency emergencyOf(long userId, Budget budget, BudgetPeriod period) {
		long spent = jdbc.sql(EMERGENCY_SPENT_SQL)
				.param("userId", userId)
				.param("fromDate", period.from())
				.param("toDate", period.to())
				.query(Long.class)
				.single();
		return Emergency.of(budget.getEmergencyAmount(), spent);
	}

	private static Integer remainingRate(long remaining, long confirmed) {
		return confirmed == 0 ? null : (int) Math.floorDiv(remaining * 100, confirmed);
	}

	private int anchorDayOf(long userId) {
		return userSettingsRepository.findById(userId)
				.map(UserSettings::getBudgetAnchorDay)
				.orElse(DEFAULT_ANCHOR_DAY);
	}

	private TxDateRange txDateRange(long userId, LocalDate referenceDate) {
		return jdbc.sql(TX_DATE_RANGE_SQL)
				.param("userId", userId)
				.param("toDate", referenceDate)
				.query((rs, rowNum) -> new TxDateRange(
						rs.getObject("first_date", LocalDate.class),
						rs.getObject("last_date", LocalDate.class)))
				.single();
	}

	private static long roundToThousand(long amount) {
		return Math.round(amount / 1000.0) * 1000;
	}

	private record TxDateRange(LocalDate firstDate, LocalDate lastDate) {
	}

	private record EnvelopeSpent(int envelopeId, String name, long amount) {
	}
}
