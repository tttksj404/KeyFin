package com.finset.key_fin.payment.repository;

import java.time.LocalDate;
import java.util.Collection;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import com.finset.key_fin.payment.entity.CardBilling;

public interface CardBillingRepository extends JpaRepository<CardBilling, Long> {

	List<CardBilling> findAllByCardIdIn(Collection<Long> cardIds);
	List<CardBilling> findAllByCardIdInAndTotalAmount(Collection<Long> cardIds, long totalAmount);

	List<CardBilling> findAllByCardIdInAndBillingDateBetween(Collection<Long> cardIds, LocalDate from, LocalDate to);
}
