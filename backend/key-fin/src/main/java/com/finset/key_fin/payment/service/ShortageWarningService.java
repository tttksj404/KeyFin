package com.finset.key_fin.payment.service;

import java.time.Clock;
import java.time.Duration;
import java.time.LocalDate;
import java.time.YearMonth;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import com.finset.key_fin.account.entity.Account;
import com.finset.key_fin.account.repository.AccountRepository;
import com.finset.key_fin.notification.entity.NotificationType;
import com.finset.key_fin.notification.service.NotificationService;
import com.finset.key_fin.payment.entity.PrepareTransfer;
import com.finset.key_fin.payment.entity.TransferStatus;
import com.finset.key_fin.payment.repository.PrepareTransferRepository;
import com.finset.key_fin.payment.service.RequiredAmountService.Entry;
import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class ShortageWarningService {

	static final String TITLE = "출금 예정 계좌 잔액이 부족해졌어요";
	private static final String KEY_PREFIX = "notification:payment:shortage:";
	private static final Duration TTL = Duration.ofDays(2);

	private final PaymentCalendarService paymentCalendarService;
	private final PrepareTransferRepository prepareTransferRepository;
	private final AccountRepository accountRepository;
	private final NotificationService notificationService;
	private final StringRedisTemplate redisTemplate;
	private final Clock clock;

	public void evaluate(long userId, long accountId) {
		LocalDate today = LocalDate.now(clock);
		List<Entry> entries = entriesOf(userId, accountId, today);
		long shortage = entries.stream().mapToLong(entry -> entry.item().shortage()).sum();
		if (shortage <= 0 || !hasExecutedTransfer(userId, accountId, entries)) {
			return;
		}
		String key = KEY_PREFIX + today + ":" + accountId;
		if (!Boolean.TRUE.equals(redisTemplate.opsForValue().setIfAbsent(key, "1", TTL))) {
			return;
		}
		String accountName = accountRepository.findByIdAndUserId(accountId, userId)
				.map(account -> account.getAlias() != null ? account.getAlias() : account.getBankName())
				.orElse("출금");
		notificationService.create(userId, NotificationType.WARNING, TITLE,
				"%s 계좌에 %,d원이 더 필요해요".formatted(accountName, shortage),
				String.valueOf(accountId), true);
	}

	private List<Entry> entriesOf(long userId, long accountId, LocalDate today) {
		List<Entry> entries = new ArrayList<>(paymentCalendarService.judgedEntries(userId, YearMonth.from(today)));
		YearMonth next = YearMonth.from(today.plusDays(1));
		if (!next.equals(YearMonth.from(today))) {
			entries.addAll(paymentCalendarService.judgedEntries(userId, next));
		}
		LocalDate tomorrow = today.plusDays(1);
		return entries.stream()
				.filter(entry -> Long.valueOf(accountId).equals(entry.item().withdrawalAccountId())
						&& entry.item().shortage() != null
						&& !entry.date().isBefore(today) && !entry.date().isAfter(tomorrow))
				.toList();
	}

	private boolean hasExecutedTransfer(long userId, long accountId, List<Entry> entries) {
		Set<String> shortKeys = entries.stream()
				.filter(entry -> entry.item().shortage() > 0)
				.map(entry -> key(entry.item().fixedExpenseId(), entry.cardBillingId(), entry.date()))
				.collect(Collectors.toSet());
		return prepareTransferRepository.findAllByUserIdAndStatusOrderByIdDesc(userId, TransferStatus.EXECUTED).stream()
				.filter(transfer -> Long.valueOf(accountId).equals(transfer.getToAccountId()))
				.map(transfer -> key(transfer.getFixedExpenseId(), transfer.getCardBillingId(), transfer.getDueDate()))
				.anyMatch(shortKeys::contains);
	}

	private static String key(Long fixedExpenseId, Long cardBillingId, LocalDate dueDate) {
		return fixedExpenseId != null ? "F" + fixedExpenseId + "|" + dueDate : "B" + cardBillingId;
	}
}
