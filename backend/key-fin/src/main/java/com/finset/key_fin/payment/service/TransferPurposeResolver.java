package com.finset.key_fin.payment.service;

import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.stream.Collectors;
import org.springframework.stereotype.Component;
import com.finset.key_fin.card.entity.Card;
import com.finset.key_fin.card.repository.CardRepository;
import com.finset.key_fin.payment.entity.CardBilling;
import com.finset.key_fin.payment.entity.FixedExpense;
import com.finset.key_fin.payment.entity.PrepareTransfer;
import com.finset.key_fin.payment.repository.CardBillingRepository;
import com.finset.key_fin.payment.repository.FixedExpenseRepository;
import lombok.RequiredArgsConstructor;

@Component
@RequiredArgsConstructor
public class TransferPurposeResolver {

	private final FixedExpenseRepository fixedExpenseRepository;
	private final CardBillingRepository cardBillingRepository;
	private final CardRepository cardRepository;

	public String nameOf(PrepareTransfer transfer) {
		return namesOf(List.of(transfer)).get(transfer.getId());
	}

	public Map<Long, String> namesOf(Collection<PrepareTransfer> transfers) {
		Map<Long, String> expenseNames = fixedExpenseRepository.findAllById(
						transfers.stream().map(PrepareTransfer::getFixedExpenseId).filter(Objects::nonNull).toList())
				.stream().collect(Collectors.toMap(FixedExpense::getId, FixedExpense::getName));
		Map<Long, Long> billingCard = cardBillingRepository.findAllById(
						transfers.stream().map(PrepareTransfer::getCardBillingId).filter(Objects::nonNull).toList())
				.stream().collect(Collectors.toMap(CardBilling::getId, CardBilling::getCardId));
		Map<Long, String> cardNames = cardRepository.findAllById(billingCard.values()).stream()
				.collect(Collectors.toMap(Card::getId, Card::getCardName, (a, b) -> a));
		Map<Long, String> names = new HashMap<>();
		for (PrepareTransfer transfer : transfers) {
			String name = transfer.getFixedExpenseId() != null
					? expenseNames.get(transfer.getFixedExpenseId())
					: cardNames.get(billingCard.get(transfer.getCardBillingId()));
			names.put(transfer.getId(), name != null ? name : "결제 준비");
		}
		return names;
	}
}
