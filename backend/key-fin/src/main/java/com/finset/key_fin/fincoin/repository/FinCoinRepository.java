package com.finset.key_fin.fincoin.repository;

import com.finset.key_fin.fincoin.entity.FinCoin;
import com.finset.key_fin.fincoin.entity.FinCoinReason;
import org.springframework.data.domain.Limit;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

public interface FinCoinRepository extends JpaRepository<FinCoin, Long> {

	boolean existsByUserIdAndGrantDateAndReasonCode(Long userId, LocalDate grantDate, FinCoinReason reasonCode);

	Optional<FinCoin> findFirstByUserIdOrderByIdDesc(Long userId);

	List<FinCoin> findByUserIdOrderByIdDesc(Long userId, Limit limit);

	List<FinCoin> findByUserIdAndIdLessThanOrderByIdDesc(Long userId, Long cursor, Limit limit);
}
