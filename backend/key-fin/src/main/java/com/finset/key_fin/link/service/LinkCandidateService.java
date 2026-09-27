package com.finset.key_fin.link.service;

import com.finset.key_fin.account.entity.Account;
import com.finset.key_fin.card.entity.Card;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.link.client.FinanceAccountClient;
import com.finset.key_fin.link.client.FinanceCardClient;
import com.finset.key_fin.link.dto.response.FinanceAccount;
import com.finset.key_fin.link.dto.response.FinanceCard;
import com.finset.key_fin.link.dto.response.LinkCandidatesResponse;
import com.finset.key_fin.link.dto.response.LinkCandidatesResponse.AccountCandidate;
import com.finset.key_fin.link.dto.response.LinkCandidatesResponse.CardCandidate;
import com.finset.key_fin.link.exception.LinkErrorCode;
import com.finset.key_fin.link.service.AssetSyncService.SyncedAssets;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class LinkCandidateService {

	private final UserRepository userRepository;
	private final FinanceAccountClient financeAccountClient;
	private final FinanceCardClient financeCardClient;
	private final AssetSyncService assetSyncService;

	public LinkCandidatesResponse getCandidates(long userId) {
		User user = userRepository.findByIdAndDeletedAtIsNull(userId)
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_NOT_FOUND));
		if (!user.isFinanceConnected()) {
			throw new BusinessException(LinkErrorCode.FINANCE_NOT_CONNECTED);
		}

		List<FinanceAccount> financeAccounts = financeAccountClient.findAccounts(user.getFinUserKey());
		List<FinanceCard> financeCards = financeCardClient.findCards(user.getFinUserKey());
		SyncedAssets synced = assetSyncService.sync(userId, financeAccounts, financeCards);

		List<AccountCandidate> accounts = financeAccounts.stream()
				.filter(FinanceAccount::isDemandDeposit)
				.map(account -> {
					Account saved = synced.accountsByNo().get(account.accountNo());
					return new AccountCandidate(
							saved.getId(),
							account.accountNo(),
							account.bankCode(),
							account.bankName(),
							account.accountBalance(),
							saved.isManaged()
					);
				})
				.toList();
		List<CardCandidate> cards = financeCards.stream()
				.map(card -> {
					Card saved = synced.cardsByNo().get(card.cardNo());
					return new CardCandidate(
							saved.getId(),
							card.cardNo(),
							card.cardIssuerName(),
							card.cardName(),
							card.withdrawalAccountNo(),
							saved.isManaged()
					);
				})
				.toList();

		return new LinkCandidatesResponse(accounts, cards);
	}
}
