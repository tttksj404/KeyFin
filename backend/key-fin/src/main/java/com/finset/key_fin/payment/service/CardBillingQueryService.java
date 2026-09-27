package com.finset.key_fin.payment.service;

import java.time.Clock;
import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.time.temporal.TemporalAdjusters;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.finset.key_fin.card.entity.Card;
import com.finset.key_fin.card.repository.CardRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.exception.CommonErrorCode;
import com.finset.key_fin.payment.dto.response.CardBillingDetailResponse;
import com.finset.key_fin.payment.dto.response.CardBillingDetailResponse.Approval;
import com.finset.key_fin.payment.dto.response.CardBillingDetailResponse.EstimatedDetail;
import com.finset.key_fin.payment.dto.response.CardBillingSummaryResponse;
import com.finset.key_fin.payment.dto.response.CardBillingSummaryResponse.CardSummary;
import com.finset.key_fin.payment.dto.response.CardBillingSummaryResponse.Estimated;
import com.finset.key_fin.payment.dto.response.CardBillingSummaryResponse.Statement;
import com.finset.key_fin.payment.entity.CardBilling;
import com.finset.key_fin.payment.exception.PaymentErrorCode;
import com.finset.key_fin.payment.repository.CardBillingRepository;
import com.finset.key_fin.transaction.entity.Transaction;
import com.finset.key_fin.transaction.repository.TransactionRepository;
import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class CardBillingQueryService {

	static final int DEFAULT_LOOKBACK_MONTHS = 1;
	static final int MAX_RANGE_MONTHS = 12;
	private static final DateTimeFormatter MONTH_FORMAT = DateTimeFormatter.ofPattern("yyyyMM");
	private static final Comparator<CardBilling> LATEST_FIRST = Comparator.comparing(CardBilling::getBillingDate).reversed();

	private final CardRepository cardRepository;
	private final CardBillingRepository cardBillingRepository;
	private final TransactionRepository transactionRepository;
	private final Clock clock;

	@Transactional(readOnly = true)
	public CardBillingSummaryResponse summary(long userId) {
		Cycle cycle = Cycle.at(LocalDate.now(clock));
		List<Card> cards = cardRepository.findAllByUserIdAndManagedTrueOrderByIdAsc(userId);
		Map<Long, CardBilling> latest = cardBillingRepository
				.findAllByCardIdIn(cards.stream().map(Card::getId).toList()).stream()
				.collect(Collectors.toMap(CardBilling::getCardId, Function.identity(),
						(a, b) -> a.getBillingDate().isAfter(b.getBillingDate()) ? a : b));
		List<CardSummary> summaries = cards.stream().map(card -> {
			List<Transaction> approvals = approvalsOf(card, cycle);
			CardBilling billing = latest.get(card.getId());
			return new CardSummary(card.getId(), card.getCardName(), card.getWithdrawalWeekday(), accountIdOf(card),
					new Estimated(sum(approvals), approvals.size(), cycle.withdrawalDate(card)),
					billing == null ? null : Statement.of(billing, card));
		}).toList();
		return new CardBillingSummaryResponse(cycle.today, cycle.monday, cycle.nextBillingDate, summaries);
	}

	/** from·to는 발행 월(yyyyMM). 기본 전월~이번 달, 최대 12개월. */
	@Transactional(readOnly = true)
	public CardBillingDetailResponse detail(long userId, long cardId, String from, String to) {
		Card card = cardRepository.findByIdAndUserId(cardId, userId)
				.orElseThrow(() -> new BusinessException(PaymentErrorCode.CARD_NOT_FOUND));
		Cycle cycle = Cycle.at(LocalDate.now(clock));
		YearMonth thisMonth = YearMonth.from(cycle.today);
		YearMonth toMonth = to == null ? thisMonth : parseMonth(to);
		YearMonth fromMonth = from == null ? toMonth.minusMonths(DEFAULT_LOOKBACK_MONTHS) : parseMonth(from);
		if (fromMonth.isAfter(toMonth) || fromMonth.plusMonths(MAX_RANGE_MONTHS).isBefore(toMonth.plusMonths(1))) {
			throw new BusinessException(CommonErrorCode.INVALID_INPUT_VALUE);
		}
		List<Transaction> approvals = approvalsOf(card, cycle);
		List<Statement> statements = cardBillingRepository
				.findAllByCardIdInAndBillingDateBetween(List.of(cardId), fromMonth.atDay(1), toMonth.atEndOfMonth()).stream()
				.sorted(LATEST_FIRST)
				.map(billing -> Statement.of(billing, card))
				.toList();
		return new CardBillingDetailResponse(cycle.today, cycle.monday, cycle.nextBillingDate,
				card.getId(), card.getCardName(), card.getWithdrawalWeekday(), accountIdOf(card),
				new EstimatedDetail(sum(approvals), cycle.withdrawalDate(card), approvals.stream().map(Approval::of).toList()),
				fromMonth.format(MONTH_FORMAT), toMonth.format(MONTH_FORMAT), statements);
	}

	private List<Transaction> approvalsOf(Card card, Cycle cycle) {
		return transactionRepository.findLiveCardApprovals(card.getId(), cycle.monday, cycle.today);
	}

	private static long sum(List<Transaction> approvals) {
		return approvals.stream().mapToLong(Transaction::getAmount).sum();
	}

	private static Long accountIdOf(Card card) {
		return card.getWithdrawalAccount() == null ? null : card.getWithdrawalAccount().getId();
	}

	private static YearMonth parseMonth(String month) {
		try {
			return YearMonth.parse(month, MONTH_FORMAT);
		} catch (DateTimeParseException e) {
			throw new BusinessException(CommonErrorCode.INVALID_INPUT_VALUE);
		}
	}

	/** 청구 주기: 이번 주 월요일 ~ 오늘 승인이 다음 월요일에 발행되고, 출금 요일에 나간다. */
	private record Cycle(LocalDate today, LocalDate monday, LocalDate nextBillingDate) {
		static Cycle at(LocalDate today) {
			LocalDate monday = today.with(TemporalAdjusters.previousOrSame(DayOfWeek.MONDAY));
			return new Cycle(today, monday, monday.plusWeeks(1));
		}

		LocalDate withdrawalDate(Card card) {
			return card.getWithdrawalWeekday() == null ? null : nextBillingDate.plusDays(card.getWithdrawalWeekday() - 1L);
		}
	}
}
