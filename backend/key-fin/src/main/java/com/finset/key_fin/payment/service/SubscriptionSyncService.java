package com.finset.key_fin.payment.service;

import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;
import java.util.stream.Collectors;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.finset.key_fin.card.entity.Card;
import com.finset.key_fin.card.repository.CardRepository;
import com.finset.key_fin.notification.entity.NotificationType;
import com.finset.key_fin.notification.service.NotificationService;
import com.finset.key_fin.payment.client.FinanceSubscriptionClient;
import com.finset.key_fin.payment.dto.response.FinanceSubscription;
import com.finset.key_fin.payment.entity.FixedExpense;
import com.finset.key_fin.payment.repository.FixedExpenseRepository;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.repository.UserRepository;

import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class SubscriptionSyncService {

	private final FinanceSubscriptionClient financeSubscriptionClient;
	private final FixedExpenseRepository fixedExpenseRepository;
	private final UserRepository userRepository;
	private final CardRepository cardRepository;
	private final NotificationService notificationService;

	@Transactional
	public SyncResult sync(long userId) {
		User user = userRepository.getReferenceById(userId);
		String userKey = user.getFinUserKey();
		if (userKey == null) {
			return SyncResult.NOT_CONNECTED;
		}

		List<FinanceSubscription> remote = financeSubscriptionClient.findSubscriptions(userKey);
		Map<String, FixedExpense> existing = fixedExpenseRepository
				.findAllByUserIdAndFinSubscriptionIdIsNotNull(userId).stream()
				.collect(Collectors.toMap(FixedExpense::getFinSubscriptionId, Function.identity()));
		List<Card> managedCards = cardRepository.findAllByUserIdAndManagedTrueOrderByIdAsc(userId);

		int created = 0, updated = 0, deactivated = 0, skipped = 0;
		Set<String> seen = new HashSet<>();
		for (FinanceSubscription subscription : remote) {
			if (!subscription.isMonthly()) {
				skipped++;
				continue;
			}
			seen.add(subscription.subscriptionId());
			FixedExpense row = existing.get(subscription.subscriptionId());
			int paymentDay = subscription.nextPayment().getDayOfMonth();
			if (subscription.isActive()) {
				if (row == null) {
					FixedExpense saved = fixedExpenseRepository.save(FixedExpense.sync(user, subscription.subscriptionId(),
							subscription.subscriptionName(), subscription.amount(), paymentDay));
					resolveCard(userId, saved, managedCards);
					created++;
				} else {
					row.syncFrom(subscription.subscriptionName(), subscription.amount(), paymentDay);
					updated++;
				}
			} else if (row != null && row.isActive()) {
				row.deactivate();
				deactivated++;
			}
		}
		for (FixedExpense row : existing.values()) {
			if (row.isActive() && !seen.contains(row.getFinSubscriptionId())) {
				row.deactivate();
				deactivated++;
			}
		}
		return new SyncResult(true, created, updated, deactivated, skipped);
	}

	/** 금융망 정기결제 조회에는 결제 카드가 없다. 카드가 한 장이면 그 카드로, 여러 장이면 사용자에게 묻는다. */
	private void resolveCard(long userId, FixedExpense expense, List<Card> managedCards) {
		if (managedCards.size() == 1) {
			expense.assignCard(managedCards.get(0).getId());
		} else if (managedCards.size() > 1) {
			notificationService.create(userId, NotificationType.SUBSCRIPTION_CARD,
					expense.getName() + " 결제 카드를 알려 주세요",
					"결제 카드를 지정하면 다음 결제도 코치 예측에 반영돼요.",
					String.valueOf(expense.getId()), true);
		}
	}

	public record SyncResult(boolean connected, int created, int updated, int deactivated, int skipped) {

		static final SyncResult NOT_CONNECTED = new SyncResult(false, 0, 0, 0, 0);
	}
}
