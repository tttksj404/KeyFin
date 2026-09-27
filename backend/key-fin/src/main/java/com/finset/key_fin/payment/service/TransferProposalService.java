package com.finset.key_fin.payment.service;

import java.time.Clock;
import java.time.LocalDate;
import java.time.YearMonth;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.finset.key_fin.account.entity.Account;
import com.finset.key_fin.account.repository.AccountRepository;
import com.finset.key_fin.payment.dto.response.PaymentCalendarResponse.CalendarItemType;
import com.finset.key_fin.payment.dto.response.PaymentCalendarResponse.Item;
import com.finset.key_fin.payment.entity.AuditLog;
import com.finset.key_fin.payment.entity.AuditLog.AuditAction;
import com.finset.key_fin.payment.entity.PrepareTransfer;
import com.finset.key_fin.payment.event.TransferProposed;
import com.finset.key_fin.payment.repository.AuditLogRepository;
import com.finset.key_fin.payment.repository.PrepareTransferRepository;
import com.finset.key_fin.payment.service.RequiredAmountService.Entry;
import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class TransferProposalService {

	static final String REASON_EXPIRED = "출금일 경과";
	static final String REASON_RESOLVED = "부족액 해소";

	private final PaymentCalendarService paymentCalendarService;
	private final PrepareTransferRepository prepareTransferRepository;
	private final AccountRepository accountRepository;
	private final AuditLogRepository auditLogRepository;
	private final ApplicationEventPublisher events;
	private final Clock clock;

	@Transactional
	public ProposalResult propose(long userId) {
		LocalDate today = LocalDate.now(clock);
		LocalDate tomorrow = today.plusDays(1);
		List<PrepareTransfer> rows = prepareTransferRepository.findAllByUserIdOrderByIdDesc(userId);
		int canceled = expire(userId, rows, today);

		Account income = accountRepository.findAllByUserIdAndIncomeTrue(userId).stream()
				.filter(Account::isManaged).findFirst().orElse(null);
		if (income == null) {
			return new ProposalResult(false, 0, 0, canceled);
		}

		Map<String, PrepareTransfer> byKey = new HashMap<>();
		rows.forEach(t -> byKey.put(key(t), t));
		Set<String> seen = new HashSet<>();
		int created = 0, updated = 0, reopened = 0;
		Set<Long> notifyAccounts = new HashSet<>();
		for (Entry entry : entriesIn(userId, today, tomorrow)) {
			Item item = entry.item();
			if (item.shortage() == null || item.shortage() <= 0
					|| item.withdrawalAccountId() == null || item.withdrawalAccountId().equals(income.getId())
					|| (item.type() == CalendarItemType.CARD_BILL && entry.cardBillingId() == null)) {
				continue;
			}
			String key = key(item.fixedExpenseId(), entry.cardBillingId(), entry.date());
			seen.add(key);
			PrepareTransfer existing = byKey.get(key);
			if (existing != null && existing.isProposed()) {
				if (existing.getRequiredAmount() != item.shortage()) {
					existing.updateRequiredAmount(item.shortage());
					updated++;
				}
				continue;
			}
			if (existing != null) {
				if (existing.isFailed()) {
					existing.reopen(today, item.shortage());
					notifyAccounts.add(item.withdrawalAccountId());
					reopened++;
				}
				continue;
			}
			PrepareTransfer transfer = item.type() == CalendarItemType.CARD_BILL
					? PrepareTransfer.proposeForCardBilling(userId, entry.cardBillingId(), today, entry.date(),
							item.shortage(), income.getId(), item.withdrawalAccountId())
					: PrepareTransfer.proposeForFixedExpense(userId, item.fixedExpenseId(), today, entry.date(),
							item.shortage(), income.getId(), item.withdrawalAccountId());
			prepareTransferRepository.save(transfer);
			notifyAccounts.add(item.withdrawalAccountId());
			created++;
		}
		for (PrepareTransfer transfer : byKey.values()) {
			if (transfer.isProposed() && !seen.contains(key(transfer)) && !transfer.getDueDate().isBefore(today)) {
				cancel(userId, transfer, REASON_RESOLVED);
				canceled++;
			}
		}
		notifyAccounts.forEach(accountId -> events.publishEvent(new TransferProposed(userId, accountId)));
		return new ProposalResult(true, created + reopened, updated, canceled);
	}

	private int expire(long userId, List<PrepareTransfer> rows, LocalDate today) {
		int canceled = 0;
		for (PrepareTransfer transfer : rows) {
			if (transfer.isProposed() && transfer.getDueDate().isBefore(today)) {
				cancel(userId, transfer, REASON_EXPIRED);
				canceled++;
			}
		}
		return canceled;
	}

	private void cancel(long userId, PrepareTransfer transfer, String reason) {
		transfer.cancel(reason);
		auditLogRepository.save(AuditLog.transfer(userId, AuditAction.CANCEL, transfer.getId(),
				reason + " — 출금일 " + transfer.getDueDate() + ", 제안액 " + transfer.getRequiredAmount()));
	}

	private List<Entry> entriesIn(long userId, LocalDate from, LocalDate to) {
		List<Entry> entries = new ArrayList<>(paymentCalendarService.judgedEntries(userId, YearMonth.from(from)));
		if (!YearMonth.from(to).equals(YearMonth.from(from))) {
			entries.addAll(paymentCalendarService.judgedEntries(userId, YearMonth.from(to)));
		}
		return entries.stream()
				.filter(entry -> !entry.date().isBefore(from) && !entry.date().isAfter(to))
				.toList();
	}

	private static String key(PrepareTransfer transfer) {
		return key(transfer.getFixedExpenseId(), transfer.getCardBillingId(), transfer.getDueDate());
	}

	/** 고정지출은 출금일마다 한 건, 카드 청구서는 한 장에 한 건. */
	private static String key(Long fixedExpenseId, Long cardBillingId, LocalDate dueDate) {
		return fixedExpenseId != null ? "F" + fixedExpenseId + "|" + dueDate : "B" + cardBillingId;
	}

	public record ProposalResult(boolean incomeAccountFound, int created, int updated, int canceled) {
	}
}
