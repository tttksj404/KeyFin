package com.finset.key_fin.payment.service;

import java.time.Clock;
import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.format.DateTimeFormatter;
import java.time.temporal.TemporalAdjusters;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.finset.key_fin.account.entity.Account;
import com.finset.key_fin.account.repository.AccountRepository;
import com.finset.key_fin.card.entity.Card;
import com.finset.key_fin.card.repository.CardRepository;
import com.finset.key_fin.payment.dto.response.PaymentCalendarResponse;
import com.finset.key_fin.payment.dto.response.PaymentCalendarResponse.Day;
import com.finset.key_fin.payment.dto.response.PaymentCalendarResponse.Item;
import com.finset.key_fin.payment.entity.CardBilling;
import com.finset.key_fin.payment.entity.FixedExpense;
import com.finset.key_fin.payment.repository.CardBillingRepository;
import com.finset.key_fin.payment.repository.FixedExpenseRepository;
import com.finset.key_fin.payment.service.RequiredAmountService.Entry;
import com.finset.key_fin.transaction.repository.TransactionRepository;
import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class PaymentCalendarService {

	private static final DateTimeFormatter MONTH_FORMAT = DateTimeFormatter.ofPattern("yyyyMM");
	private static final Comparator<Item> ITEM_ORDER = Comparator
			.comparing(Item::type)
			.thenComparing(Item::amount, Comparator.reverseOrder());

	private final FixedExpenseRepository fixedExpenseRepository;
	private final CardRepository cardRepository;
	private final CardBillingRepository cardBillingRepository;
	private final TransactionRepository transactionRepository;
	private final AccountRepository accountRepository;
	private final RequiredAmountService requiredAmountService;
	private final Clock clock;

	@Transactional(readOnly = true)
	public PaymentCalendarResponse getCalendar(long userId, YearMonth month) {
		Map<LocalDate, List<Item>> byDate = new TreeMap<>();
		for (Entry entry : judgedEntries(userId, month)) {
			if (YearMonth.from(entry.date()).equals(month)) {
				byDate.computeIfAbsent(entry.date(), date -> new ArrayList<>()).add(entry.item());
			}
		}
		List<Day> days = byDate.entrySet().stream()
				.map(entry -> new Day(entry.getKey(), entry.getValue().stream().sorted(ITEM_ORDER).toList()))
				.toList();
		return new PaymentCalendarResponse(month.format(MONTH_FORMAT), days);
	}

	/** 고정지출·카드 청구 항목을 모아 잔액 판정까지 마친 목록. 달력 월 밖 날짜(전월 말 청구서 등)도 섞여 있다. */
	@Transactional(readOnly = true)
	public List<Entry> judgedEntries(long userId, YearMonth month) {
		LocalDate today = LocalDate.now(clock);
		List<Entry> entries = new ArrayList<>();
		for (FixedExpense expense : fixedExpenseRepository.findAllByUserIdAndActiveTrueOrderByIdAsc(userId)) {
			entries.add(new Entry(expense.paymentDateIn(month), Item.of(expense)));
		}
		entries.addAll(cardBillEntries(userId, month, today));
		Map<Long, Long> balances = accountRepository.findAllByUserId(userId).stream()
				.collect(Collectors.toMap(Account::getId, Account::getBalance));
		return requiredAmountService.judge(entries, balances, today);
	}

	private List<Entry> cardBillEntries(long userId, YearMonth month, LocalDate today) {
		Map<Long, Card> cards = cardRepository.findAllByUserIdAndManagedTrueOrderByIdAsc(userId).stream()
				.filter(card -> card.getWithdrawalWeekday() != null)
				.collect(Collectors.toMap(Card::getId, Function.identity()));
		if (cards.isEmpty()) {
			return List.of();
		}
		List<Entry> entries = new ArrayList<>();
		List<CardBilling> billings = cardBillingRepository.findAllByCardIdInAndBillingDateBetween(
				cards.keySet(), month.atDay(1).minusWeeks(1), month.atEndOfMonth());
		for (CardBilling billing : billings) {
			Card card = cards.get(billing.getCardId());
			LocalDate date = billing.isPaid()
					? billing.getPaidAt().toLocalDate()
					: billing.withdrawalDate(card.getWithdrawalWeekday());
			entries.add(new Entry(date, Item.of(billing, card.getCardName(), accountIdOf(card)), billing.getId()));
		}
		LocalDate cycleMonday = today.with(TemporalAdjusters.previousOrSame(DayOfWeek.MONDAY));
		LocalDate nextBillingDate = cycleMonday.plusWeeks(1);
		for (Card card : cards.values()) {
			LocalDate date = nextBillingDate.plusDays(card.getWithdrawalWeekday() - 1L);
			if (!YearMonth.from(date).equals(month)) {
				continue;
			}
			long amount = transactionRepository.sumLiveCardApprovals(card.getId(), cycleMonday, today);
			if (amount > 0) {
				entries.add(new Entry(date, Item.estimatedCardBill(card.getId(), card.getCardName(), amount, accountIdOf(card))));
			}
		}
		return entries;
	}

	private static Long accountIdOf(Card card) {
		return card.getWithdrawalAccount() == null ? null : card.getWithdrawalAccount().getId();
	}
}
