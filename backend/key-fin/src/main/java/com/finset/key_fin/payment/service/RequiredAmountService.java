package com.finset.key_fin.payment.service;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;
import com.finset.key_fin.payment.dto.response.PaymentCalendarResponse.Item;

@Service
public class RequiredAmountService {

	public record Entry(LocalDate date, Item item, Long cardBillingId) {
		public Entry(LocalDate date, Item item) {
			this(date, item, null);
		}
	}

	private static final Comparator<Entry> WITHDRAWAL_ORDER = Comparator
			.comparing(Entry::date)
			.thenComparing(entry -> entry.item().amount(), Comparator.reverseOrder());

	/**
	 * 같은 출금 계좌의 오늘 이후 항목을 날짜 → 금액 내림차순으로 잔액에서 순차 차감해 prepared/shortage를 채운다.
	 * 출금 계좌가 없거나 과거이거나 이미 판정된 항목은 그대로 둔다.
	 */
	public List<Entry> judge(List<Entry> entries, Map<Long, Long> balanceByAccountId, LocalDate today) {
		Map<Long, List<Integer>> pendingByAccount = new HashMap<>();
		for (int i = 0; i < entries.size(); i++) {
			Entry entry = entries.get(i);
			Long accountId = entry.item().withdrawalAccountId();
			if (accountId == null || entry.date().isBefore(today) || entry.item().prepared() != null
					|| !balanceByAccountId.containsKey(accountId)) {
				continue;
			}
			pendingByAccount.computeIfAbsent(accountId, id -> new ArrayList<>()).add(i);
		}
		List<Entry> judged = new ArrayList<>(entries);
		for (Map.Entry<Long, List<Integer>> pending : pendingByAccount.entrySet()) {
			long remaining = balanceByAccountId.get(pending.getKey());
			List<Integer> order = pending.getValue().stream()
					.sorted(Comparator.comparing(entries::get, WITHDRAWAL_ORDER))
					.toList();
			for (int index : order) {
				Entry entry = entries.get(index);
				long amount = entry.item().amount();
				long shortage = Math.max(0, amount - remaining);
				judged.set(index, new Entry(entry.date(), entry.item().judged(shortage == 0, shortage), entry.cardBillingId()));
				remaining = Math.max(0, remaining - amount);
			}
		}
		return judged;
	}
}
