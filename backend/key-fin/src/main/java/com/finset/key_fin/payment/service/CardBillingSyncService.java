package com.finset.key_fin.payment.service;

import java.time.Clock;
import java.time.LocalDate;
import java.time.YearMonth;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.finset.key_fin.card.entity.Card;
import com.finset.key_fin.card.repository.CardRepository;
import com.finset.key_fin.payment.client.FinanceCardBillingClient;
import com.finset.key_fin.payment.dto.response.FinanceBillingStatement;
import com.finset.key_fin.payment.entity.CardBilling;
import com.finset.key_fin.payment.repository.CardBillingRepository;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class CardBillingSyncService {

	private static final int STATEMENT_LOOKBACK_MONTHS = 1;

	private final FinanceCardBillingClient financeCardBillingClient;
	private final CardRepository cardRepository;
	private final CardBillingRepository cardBillingRepository;
	private final UserRepository userRepository;
	private final Clock clock;

	@Transactional
	public SyncResult sync(long userId) {
		User user = userRepository.getReferenceById(userId);
		String userKey = user.getFinUserKey();
		if (userKey == null) {
			return SyncResult.NOT_CONNECTED;
		}
		List<Card> cards = cardRepository.findAllByUserIdAndManagedTrueOrderByIdAsc(userId);
		if (cards.isEmpty()) {
			return new SyncResult(true, 0, 0);
		}
		Map<String, CardBilling> byKey = cardBillingRepository
				.findAllByCardIdIn(cards.stream().map(Card::getId).toList()).stream()
				.collect(Collectors.toMap(billing -> key(billing.getCardId(), billing.getBillingDate()), Function.identity()));
		YearMonth thisMonth = YearMonth.from(LocalDate.now(clock));
		List<CardBilling> created = new ArrayList<>();
		int updated = 0;
		for (Card card : cards) {
			List<FinanceBillingStatement> statements = financeCardBillingClient.findBillingStatements(
					userKey, card.getFinCardNo(), card.getCvc(), thisMonth.minusMonths(STATEMENT_LOOKBACK_MONTHS), thisMonth);
			for (FinanceBillingStatement statement : statements) {
				CardBilling row = byKey.get(key(card.getId(), statement.issuedOn()));
				if (row == null) {
					created.add(CardBilling.sync(
							card.getId(), statement.issuedOn(), statement.amount(), statement.isPaid(), statement.paidAt()));
				} else {
					row.syncFrom(statement.amount(), statement.isPaid(), statement.paidAt());
					updated++;
				}
			}
		}
		cardBillingRepository.saveAll(created);
		return new SyncResult(true, created.size(), updated);
	}

	private static String key(long cardId, LocalDate billingDate) {
		return cardId + "|" + billingDate;
	}

	public record SyncResult(boolean connected, int created, int updated) {
		static final SyncResult NOT_CONNECTED = new SyncResult(false, 0, 0);
	}
}
