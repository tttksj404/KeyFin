package com.finset.key_fin.coaching.service;

import java.time.LocalDate;
import java.time.YearMonth;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

import org.springframework.stereotype.Component;

import com.finset.key_fin.account.entity.Account;
import com.finset.key_fin.card.entity.Card;
import com.finset.key_fin.coaching.dto.FdtSnapshot;
import com.finset.key_fin.payment.entity.CardBilling;
import com.finset.key_fin.payment.entity.ExpenseType;
import com.finset.key_fin.payment.entity.FixedExpense;

/** 계좌·카드·미납 청구서·고정지출·예산을 FDT snapshot 으로 묶는다. */
@Component
public class FdtSnapshotAssembler {

	/** 신용·체크 구분 컬럼이 없어 전부 CREDIT 으로 보낸다. */
	private static final String CARD_KIND = "CREDIT";
	private static final String SOURCE_LIVE = "LIVE";
	private static final String MONTHLY = "MONTHLY";
	private static final String FIXED_EXPENSE = "fixed_expense";
	/** 스키마는 fixed_expense 에 fixed_group 을 필수로 요구한다. 대출 상환은 대응 묶음이 없어 별도 kind 로 보낸다. */
	private static final String DEBT_SERVICE = "debt_service";

	private static final Map<ExpenseType, String> FIXED_GROUP = Map.of(
			ExpenseType.RENT, "주거",
			ExpenseType.UTILITY, "공과금",
			ExpenseType.SUBSCRIPTION, "구독·멤버십"
	);

	public FdtSnapshot assemble(
			LocalDate asOf,
			List<Account> accounts,
			List<Card> cards,
			List<CardBilling> unpaidBillings,
			List<FixedExpense> fixedExpenses,
			long emergencyAmount,
			Map<String, Long> budgets
	) {
		List<FdtSnapshot.Account> snapshotAccounts = accounts.stream()
				.map(account -> new FdtSnapshot.Account(
						id(account.getId()), account.getBalance(), account.isIncome()))
				.toList();
		List<FdtSnapshot.Card> snapshotCards = cards(cards, unpaidBillings);
		return new FdtSnapshot(
				asOf.toString(),
				SOURCE_LIVE,
				snapshotAccounts,
				snapshotCards,
				knownBills(cards, unpaidBillings, asOf),
				schedules(fixedExpenses, asOf,
						snapshotAccounts.stream().map(FdtSnapshot.Account::accountId).collect(Collectors.toSet()),
						snapshotCards.stream().map(FdtSnapshot.Card::cardId).collect(Collectors.toSet())),
				emergencyAmount,
				budgets.isEmpty() ? null : budgets,
				FdtSnapshot.Coverage.NONE
		);
	}

	/**
	 * opening_payable_krw 는 known_bills 합계와 같아야 한다. 어긋나면 엔진이 OPENING_PAYABLE_MISMATCH 로 거부하므로
	 * 같은 목록에서 계산한다.
	 */
	private List<FdtSnapshot.Card> cards(List<Card> cards, List<CardBilling> unpaidBillings) {
		return cards.stream()
				.filter(card -> card.getWithdrawalWeekday() != null)
				.map(card -> new FdtSnapshot.Card(
						id(card.getId()),
						CARD_KIND,
						card.getWithdrawalAccount() == null ? "" : id(card.getWithdrawalAccount().getId()),
						unpaidBillings.stream()
								.filter(billing -> billing.getCardId().equals(card.getId()))
								.mapToLong(CardBilling::getTotalAmount)
								.sum(),
						card.getWithdrawalWeekday() - 1
				))
				.toList();
	}

	/** 엔진은 due_date <= as_of 인 청구서를 거부한다(PAST_BILL_DUE_DATE). 당일·미납분은 내일 출금으로 보내 금액을 남긴다. */
	private List<FdtSnapshot.KnownBill> knownBills(List<Card> cards, List<CardBilling> unpaidBillings, LocalDate asOf) {
		Map<Long, Integer> weekdayByCardId = new LinkedHashMap<>();
		for (Card card : cards) {
			if (card.getWithdrawalWeekday() != null) {
				weekdayByCardId.put(card.getId(), card.getWithdrawalWeekday());
			}
		}
		List<FdtSnapshot.KnownBill> bills = new ArrayList<>();
		for (CardBilling billing : unpaidBillings) {
			Integer weekday = weekdayByCardId.get(billing.getCardId());
			if (weekday == null) {
				continue;
			}
			LocalDate dueDate = billing.withdrawalDate(weekday);
			bills.add(new FdtSnapshot.KnownBill(
					id(billing.getId()),
					id(billing.getCardId()),
					(dueDate.isAfter(asOf) ? dueDate : asOf.plusDays(1)).toString(),
					billing.getTotalAmount()
			));
		}
		return bills;
	}

	/**
	 * 카드대금은 known_bills 로 따로 나가므로 일정에서 뺀다. 두 번 세면 예측이 그만큼 비관적이 된다.
	 * FDT 는 일정의 card_id·account_id 가 snapshot 에 없으면 INVALID_SCHEDULE_* 로 트윈 전체를 거부하므로 그 일정만 뺀다.
	 */
	private List<FdtSnapshot.Schedule> schedules(List<FixedExpense> fixedExpenses, LocalDate asOf,
			Set<String> accountIds, Set<String> cardIds) {
		List<FdtSnapshot.Schedule> schedules = new ArrayList<>();
		for (FixedExpense expense : fixedExpenses) {
			if (expense.getExpenseType() == ExpenseType.CARD_BILL || expense.getAmount() == null) {
				continue;
			}
			String accountId = expense.isSynced() || expense.getWithdrawalAccountId() == null
					? null : id(expense.getWithdrawalAccountId());
			String cardId = expense.isSynced() && expense.getCardId() != null ? id(expense.getCardId()) : null;
			if (!(cardId != null ? cardIds.contains(cardId) : accountIds.contains(accountId))) {
				continue;
			}
			String fixedGroup = FIXED_GROUP.get(expense.getExpenseType());
			schedules.add(new FdtSnapshot.Schedule(
					id(expense.getId()),
					fixedGroup == null ? DEBT_SERVICE : FIXED_EXPENSE,
					expense.getAmount(),
					MONTHLY,
					nextDate(expense, asOf).toString(),
					expense.getPaymentDay(),
					fixedGroup,
					accountId,
					cardId
			));
		}
		return schedules;
	}

	/**
	 * FDT 는 next_date 가 기준일(as_of) 이하인 일정을 PAST_SCHEDULE 로 보고 트윈 전체를 거부한다.
	 * 결제일이 오늘이면 이번 달 회차는 이미 기준일에 속하므로 다음 달 회차를 보낸다(청구서의 dueDate 처리와 같은 경계).
	 */
	private LocalDate nextDate(FixedExpense expense, LocalDate asOf) {
		LocalDate thisMonth = expense.paymentDateIn(YearMonth.from(asOf));
		return thisMonth.isAfter(asOf) ? thisMonth : expense.paymentDateIn(YearMonth.from(asOf).plusMonths(1));
	}

	public static List<CardBilling> unpaid(Collection<CardBilling> billings) {
		return billings.stream().filter(billing -> !billing.isPaid()).toList();
	}

	private static String id(Long value) {
		return String.valueOf(value);
	}
}
