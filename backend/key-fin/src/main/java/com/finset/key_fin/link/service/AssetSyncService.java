package com.finset.key_fin.link.service;

import com.finset.key_fin.account.entity.Account;
import com.finset.key_fin.account.repository.AccountRepository;
import com.finset.key_fin.card.entity.Card;
import com.finset.key_fin.card.repository.CardRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.link.dto.response.FinanceAccount;
import com.finset.key_fin.link.dto.response.FinanceCard;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * 후보 목록 조회 시 금융망 계좌·카드를 accounts/cards에 처음 한 번 적재한다.
 * 이미 저장된 자산은 건드리지 않고, 없는 자산만 is_managed=false(미선택)로 saveAll 한다.
 *
 * TODO(yr): 가입 이후 금융망에 신설된 계좌·카드는 사용자 호출이 아니라 배치(P1 FR-USR-08, 1시간 주기 + 로그인 시 1회)가
 *  감지해 is_managed=false로 등록하고 알림을 보낸다. 배치는 이 서비스의 신규 자산 선별·saveAll 로직을 재사용하고,
 *  기존 카드의 CVC·카드명·출금계좌 변경 반영도 그 배치에서 처리한다.
 */
@Service
@RequiredArgsConstructor
public class AssetSyncService {

	private final UserRepository userRepository;
	private final AccountRepository accountRepository;
	private final CardRepository cardRepository;

	public record SyncedAssets(Map<String, Account> accountsByNo, Map<String, Card> cardsByNo) {
	}

	@Transactional
	public SyncedAssets sync(long userId, List<FinanceAccount> financeAccounts, List<FinanceCard> financeCards) {
		User user = userRepository.findByIdAndDeletedAtIsNull(userId)
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_NOT_FOUND));
		LocalDateTime balanceUpdatedAt = LocalDateTime.now();

		Map<String, Account> accountsByNo = new HashMap<>(accountRepository.findAllByUserId(userId).stream()
				.collect(Collectors.toMap(Account::getFinAccountNo, Function.identity())));
		financeAccounts.stream()
				.filter(FinanceAccount::isDemandDeposit)
				.filter(account -> accountsByNo.containsKey(account.accountNo()))
				.forEach(account -> accountsByNo.get(account.accountNo())
						.updateBalanceSnapshot(account.bankName(), account.accountBalance(), balanceUpdatedAt));
		List<Account> newAccounts = financeAccounts.stream()
				.filter(FinanceAccount::isDemandDeposit)
				.filter(account -> !accountsByNo.containsKey(account.accountNo()))
				.map(account -> Account.sync(
						user,
						account.accountNo(),
						account.bankCode(),
						account.bankName(),
						account.accountBalance(),
						balanceUpdatedAt
				))
				.toList();
		accountRepository.saveAll(newAccounts)
				.forEach(account -> accountsByNo.put(account.getFinAccountNo(), account));

		Map<String, Card> cardsByNo = new HashMap<>(cardRepository.findAllByUserId(userId).stream()
				.collect(Collectors.toMap(Card::getFinCardNo, Function.identity())));
		List<Card> newCards = financeCards.stream()
				.filter(card -> !cardsByNo.containsKey(card.cardNo()))
				.map(card -> {
					Card synced = Card.sync(
							user,
							card.cardNo(),
							card.cvc(),
							card.cardIssuerCode(),
							card.cardName(),
							accountsByNo.get(card.withdrawalAccountNo())
					);
					synced.updateWithdrawalWeekday(card.withdrawalWeekday());
					return synced;
				})
				.toList();
		cardRepository.saveAll(newCards)
				.forEach(card -> cardsByNo.put(card.getFinCardNo(), card));

		return new SyncedAssets(accountsByNo, cardsByNo);
	}
}
