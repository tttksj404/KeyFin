package com.finset.key_fin.fincoin.entity;

import com.finset.key_fin.global.base.BaseEntity;
import com.finset.key_fin.user.entity.User;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.LocalDate;
import java.util.Objects;

@Getter
@Entity
@Table(name = "fin_coin")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class FinCoin extends BaseEntity {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@ManyToOne(fetch = FetchType.LAZY, optional = false)
	@JoinColumn(name = "user_id", nullable = false)
	private User user;

	@Column(nullable = false)
	private Integer delta;

	@Column(name = "balance_after", nullable = false)
	private Integer balanceAfter;

	@Enumerated(EnumType.STRING)
	@Column(name = "reason_code", nullable = false, length = 20)
	private FinCoinReason reasonCode;

	@Column(name = "grant_date", nullable = false)
	private LocalDate grantDate;

	@Column(name = "ref_id", length = 30)
	private String refId;

	public static FinCoin forPurchase(User user, LocalDate purchaseDate, long itemId, int price, int balanceBefore) {
		Objects.requireNonNull(user, "user must not be null");
		Objects.requireNonNull(purchaseDate, "purchaseDate must not be null");
		if (itemId <= 0 || price < 0 || balanceBefore < price) {
			throw new IllegalArgumentException("상품 ID는 양수이고 가격은 0 이상이며 잔액은 가격 이상이어야 합니다.");
		}

		FinCoin coin = new FinCoin();
		coin.user = user;
		coin.delta = -price;
		coin.balanceAfter = balanceBefore - price;
		coin.reasonCode = FinCoinReason.PURCHASE;
		coin.grantDate = purchaseDate;
		coin.refId = Long.toString(itemId);
		return coin;
	}

	public static FinCoin forAttendance(User user, LocalDate grantDate, int reward, int balanceBefore) {
		Objects.requireNonNull(user, "user must not be null");
		Objects.requireNonNull(grantDate, "grantDate must not be null");
		if (reward <= 0 || balanceBefore < 0) {
			throw new IllegalArgumentException("출석 지급량은 양수이고 기존 잔액은 0 이상이어야 합니다.");
		}

		FinCoin coin = new FinCoin();
		coin.user = user;
		coin.delta = reward;
		coin.balanceAfter = Math.addExact(balanceBefore, reward);
		coin.reasonCode = FinCoinReason.ATTEND;
		coin.grantDate = grantDate;
		return coin;
	}
}
