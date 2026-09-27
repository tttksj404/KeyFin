package com.finset.key_fin.coaching.service;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import com.finset.key_fin.account.entity.Account;
import com.finset.key_fin.card.entity.Card;
import com.finset.key_fin.coaching.dto.FdtSnapshot;
import com.finset.key_fin.payment.entity.CardBilling;
import com.finset.key_fin.payment.entity.ExpenseType;
import com.finset.key_fin.payment.entity.FixedExpense;
import com.finset.key_fin.user.entity.User;

class FdtSnapshotAssemblerTest {

	private static final LocalDate AS_OF = LocalDate.of(2026, 9, 10);

	private final FdtSnapshotAssembler assembler = new FdtSnapshotAssembler();

	@Test
	void 계좌_잔액과_기준일을_담는다() {
		FdtSnapshot snapshot = assemble(List.of(account(1L, 5_458_220L)), List.of(), List.of(), List.of(), 0L, Map.of());

		assertThat(snapshot.asOf()).isEqualTo("2026-09-10");
		assertThat(snapshot.source()).isEqualTo("LIVE");
		assertThat(snapshot.accounts()).containsExactly(new FdtSnapshot.Account("1", 5_458_220L, false));
		assertThat(snapshot.coverage()).isEqualTo(FdtSnapshot.Coverage.NONE);
	}

	@Test
	void 주거래_계좌의_income_플래그를_스냅샷에_전달한다() {
		Account income = account(1L, 1_000_000L);
		ReflectionTestUtils.setField(income, "income", true);

		FdtSnapshot snapshot = assemble(List.of(income), List.of(), List.of(), List.of(), 0L, Map.of());

		assertThat(snapshot.accounts()).containsExactly(new FdtSnapshot.Account("1", 1_000_000L, true));
	}

	@Test
	void 카드_미납액이_미납_청구서_합계와_일치한다() {
		Account settlement = account(1L, 1_000_000L);
		Card card = card(7L, settlement, 3);
		List<CardBilling> unpaid = List.of(billing(11L, 7L, 300_000L), billing(12L, 7L, 200_000L));

		FdtSnapshot snapshot = assemble(List.of(settlement), List.of(card), unpaid, List.of(), 0L, Map.of());

		long billSum = snapshot.knownBills().stream().mapToLong(FdtSnapshot.KnownBill::amountKrw).sum();
		assertThat(snapshot.cards()).hasSize(1);
		assertThat(snapshot.cards().get(0).openingPayableKrw()).isEqualTo(500_000L).isEqualTo(billSum);
		assertThat(snapshot.cards().get(0).kind()).isEqualTo("CREDIT");
		assertThat(snapshot.cards().get(0).settlementAccountId()).isEqualTo("1");
	}

	@Test
	void 청구서_출금일은_발행일에_출금_요일만큼_더한다() {
		Account settlement = account(1L, 0L);
		Card friday = card(7L, settlement, 5);

		FdtSnapshot snapshot = assemble(List.of(settlement), List.of(friday),
				List.of(billing(11L, 7L, 100_000L)), List.of(), 0L, Map.of());

		assertThat(snapshot.cards().get(0).paymentDelayDays()).isEqualTo(4);
		assertThat(snapshot.knownBills().get(0).dueDate()).isEqualTo("2026-09-11");
	}

	@Test
	void 출금일이_기준일_당일이거나_지난_미납_청구서는_내일_출금으로_보내고_금액은_그대로_둔다() {
		Account settlement = account(1L, 0L);
		Card thursday = card(7L, settlement, 4);
		Card wednesday = card(8L, settlement, 3);

		FdtSnapshot snapshot = assemble(List.of(settlement), List.of(thursday, wednesday),
				List.of(billing(11L, 7L, 100_000L), billing(12L, 8L, 50_000L)), List.of(), 0L, Map.of());

		assertThat(snapshot.knownBills()).extracting(FdtSnapshot.KnownBill::dueDate)
				.containsExactly("2026-09-11", "2026-09-11");
		assertThat(snapshot.knownBills()).extracting(FdtSnapshot.KnownBill::amountKrw)
				.containsExactly(100_000L, 50_000L);
		assertThat(snapshot.cards()).extracting(FdtSnapshot.Card::openingPayableKrw)
				.containsExactly(100_000L, 50_000L);
	}

	@Test
	void 출금_요일이_없는_카드와_그_청구서는_제외한다() {
		Account settlement = account(1L, 0L);
		Card unknown = card(9L, settlement, null);

		FdtSnapshot snapshot = assemble(List.of(settlement), List.of(unknown),
				List.of(billing(21L, 9L, 100_000L)), List.of(), 0L, Map.of());

		assertThat(snapshot.cards()).isEmpty();
		assertThat(snapshot.knownBills()).isEmpty();
	}

	@Test
	void 고정지출을_월주기_일정으로_보낸다() {
		FixedExpense rent = fixedExpense(31L, "월세", ExpenseType.RENT, 750_000L, 5, 1L);

		FdtSnapshot snapshot = assemble(List.of(account(1L, 0L)), List.of(), List.of(), List.of(rent), 0L, Map.of());

		FdtSnapshot.Schedule schedule = snapshot.schedules().get(0);
		assertThat(schedule.kind()).isEqualTo("fixed_expense");
		assertThat(schedule.frequency()).isEqualTo("MONTHLY");
		assertThat(schedule.amountKrw()).isEqualTo(750_000L);
		assertThat(schedule.dayOfMonth()).isEqualTo(5);
		assertThat(schedule.fixedGroup()).isEqualTo("주거");
		assertThat(schedule.accountId()).isEqualTo("1");
	}

	@Test
	void 이번달_출금일이_지났으면_다음달로_넘긴다() {
		FixedExpense passed = fixedExpense(31L, "월세", ExpenseType.RENT, 750_000L, 5, 1L);
		FixedExpense upcoming = fixedExpense(32L, "관리비", ExpenseType.UTILITY, 115_000L, 25, 1L);

		FdtSnapshot snapshot = assemble(List.of(account(1L, 0L)), List.of(), List.of(), List.of(passed, upcoming), 0L, Map.of());

		assertThat(snapshot.schedules().get(0).nextDate()).isEqualTo("2026-10-05");
		assertThat(snapshot.schedules().get(1).nextDate()).isEqualTo("2026-09-25");
	}

	/** 결제일이 기준일과 같으면 FDT 가 PAST_SCHEDULE 로 트윈 전체를 거부하므로 다음 달 회차를 보낸다(2026-09-23 라이브 장애). */
	@Test
	void 출금일이_오늘이면_다음달로_넘긴다() {
		FixedExpense today = fixedExpense(33L, "chatGPT pro", ExpenseType.SUBSCRIPTION, 100_000L, 10, 1L);

		FdtSnapshot snapshot = assemble(List.of(account(1L, 0L)), List.of(), List.of(), List.of(today), 0L, Map.of());

		assertThat(snapshot.schedules().get(0).nextDate()).isEqualTo("2026-10-10");
	}

	@Test
	void 대출은_debt_service로_보내고_fixed_group을_비운다() {
		FixedExpense loan = fixedExpense(33L, "학자금 상환", ExpenseType.LOAN, 200_000L, 15, 1L);

		FdtSnapshot snapshot = assemble(List.of(account(1L, 0L)), List.of(), List.of(), List.of(loan), 0L, Map.of());

		assertThat(snapshot.schedules()).hasSize(1);
		assertThat(snapshot.schedules().get(0).kind()).isEqualTo("debt_service");
		assertThat(snapshot.schedules().get(0).fixedGroup()).isNull();
	}

	@Test
	void 카드대금_고정지출은_청구서와_중복되므로_제외한다() {
		FixedExpense cardBill = fixedExpense(34L, "삼성카드 대금", ExpenseType.CARD_BILL, 400_000L, 10, 1L);
		FixedExpense rent = fixedExpense(31L, "월세", ExpenseType.RENT, 750_000L, 5, 1L);

		FdtSnapshot snapshot = assemble(List.of(account(1L, 0L)), List.of(), List.of(), List.of(cardBill, rent), 0L, Map.of());

		assertThat(snapshot.schedules()).hasSize(1);
		assertThat(snapshot.schedules().get(0).fixedGroup()).isEqualTo("주거");
	}

	@Test
	void 카드_정기결제는_지정된_카드로_보내고_카드를_모르면_그_일정만_뺀다() {
		Account settlement = account(1L, 0L);
		FixedExpense netflix = subscription(35L, "넷플릭스", 17_000L, 28);
		netflix.assignCard(7L);
		FixedExpense disney = subscription(36L, "디즈니+", 9_900L, 28);

		FdtSnapshot snapshot = assemble(List.of(settlement), List.of(card(7L, settlement, 3)), List.of(),
				List.of(netflix, disney), 0L, Map.of());

		assertThat(snapshot.schedules()).hasSize(1);
		assertThat(snapshot.schedules().get(0).ruleId()).isEqualTo("35");
		assertThat(snapshot.schedules().get(0).cardId()).isEqualTo("7");
		assertThat(snapshot.schedules().get(0).accountId()).isNull();
	}

	/** FDT 는 snapshot 에 없는 카드·계좌를 가리키는 일정 하나로 트윈 전체를 거부한다(2026-09-24 INVALID_SCHEDULE_ACCOUNT). */
	@Test
	void snapshot에_없는_카드나_계좌를_가리키는_일정은_뺀다() {
		Account settlement = account(1L, 0L);
		FixedExpense noWeekdayCard = subscription(35L, "넷플릭스", 17_000L, 28);
		noWeekdayCard.assignCard(8L);
		FixedExpense unmanagedAccount = fixedExpense(31L, "월세", ExpenseType.RENT, 750_000L, 5, 2L);

		FdtSnapshot snapshot = assemble(List.of(settlement), List.of(card(8L, settlement, null)), List.of(),
				List.of(noWeekdayCard, unmanagedAccount), 0L, Map.of());

		assertThat(snapshot.schedules()).isEmpty();
	}

	@Test
	void 비상금과_봉투_예산을_담는다() {
		Map<String, Long> budgets = Map.of("외식", 280_000L, "교통비", 90_000L);

		FdtSnapshot snapshot = assemble(List.of(), List.of(), List.of(), List.of(), 300_000L, budgets);

		assertThat(snapshot.reserveKrw()).isEqualTo(300_000L);
		assertThat(snapshot.budgets()).containsExactlyInAnyOrderEntriesOf(budgets);
	}

	@Test
	void 비상금_미설정은_0으로_나간다() {
		FdtSnapshot snapshot = assemble(List.of(), List.of(), List.of(), List.of(), 0L, Map.of());

		assertThat(snapshot.reserveKrw()).isZero();
		assertThat(snapshot.budgets()).isNull();
	}

	@Test
	void 미납_청구서만_골라낸다() {
		CardBilling paid = billing(11L, 7L, 300_000L);
		ReflectionTestUtils.invokeMethod(paid, "syncFrom", 300_000L, true, LocalDateTime.of(2026, 9, 2, 16, 0));

		assertThat(FdtSnapshotAssembler.unpaid(List.of(paid, billing(12L, 7L, 200_000L)))).hasSize(1);
	}

	private FdtSnapshot assemble(List<Account> accounts, List<Card> cards, List<CardBilling> unpaidBillings,
			List<FixedExpense> fixedExpenses, long emergencyAmount, Map<String, Long> budgets) {
		return assembler.assemble(AS_OF, accounts, cards, unpaidBillings, fixedExpenses, emergencyAmount, budgets);
	}

	private Account account(long id, long balance) {
		Account account = Account.sync(user(), "110" + id, "004", "국민은행", balance, LocalDateTime.of(2026, 9, 10, 3, 0));
		ReflectionTestUtils.setField(account, "id", id);
		return account;
	}

	private Card card(long id, Account settlement, Integer withdrawalWeekday) {
		Card card = Card.sync(user(), "9430" + id, "123", "삼성", "삼성카드", settlement);
		ReflectionTestUtils.setField(card, "id", id);
		ReflectionTestUtils.setField(card, "withdrawalWeekday", withdrawalWeekday);
		return card;
	}

	private CardBilling billing(long id, long cardId, long amount) {
		CardBilling billing = CardBilling.sync(cardId, LocalDate.of(2026, 9, 7), amount, false, null);
		ReflectionTestUtils.setField(billing, "id", id);
		return billing;
	}

	private FixedExpense fixedExpense(long id, String name, ExpenseType type, long amount, int paymentDay,
			long withdrawalAccountId) {
		FixedExpense expense = FixedExpense.register(user(), name, type, amount, false, paymentDay, withdrawalAccountId);
		ReflectionTestUtils.setField(expense, "id", id);
		return expense;
	}

	private FixedExpense subscription(long id, String name, long amount, int paymentDay) {
		FixedExpense expense = FixedExpense.sync(user(), "SUB" + id, name, amount, paymentDay);
		ReflectionTestUtils.setField(expense, "id", id);
		return expense;
	}

	private User user() {
		User user = User.create("keyfin-tester@example.com", "password", "정재원");
		ReflectionTestUtils.setField(user, "id", 1L);
		return user;
	}
}
