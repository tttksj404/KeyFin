package com.finset.key_fin.link.service;

import com.finset.key_fin.account.entity.Account;
import com.finset.key_fin.account.repository.AccountRepository;
import com.finset.key_fin.card.entity.Card;
import com.finset.key_fin.card.repository.CardRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.link.dto.response.LinkAssetsResponse;
import com.finset.key_fin.link.exception.LinkErrorCode;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Set;

@Service
@RequiredArgsConstructor
public class AssetLinkWriter {

	private final AccountRepository accountRepository;
	private final CardRepository cardRepository;

	@Transactional
	public LinkAssetsResponse link(long userId, Set<Long> accountIds, Set<Long> cardIds) {
		int linkedAccounts = 0;
		if (!accountIds.isEmpty()) {
			List<Account> accounts = accountRepository.findAllByIdInAndUserId(accountIds, userId);
			if (accounts.size() != accountIds.size()) {
				throw new BusinessException(LinkErrorCode.ACCOUNT_NOT_FOUND);
			}
			linkedAccounts = (int) accounts.stream().filter(Account::link).count();
		}

		int linkedCards = 0;
		if (!cardIds.isEmpty()) {
			List<Card> cards = cardRepository.findAllByIdInAndUserId(cardIds, userId);
			if (cards.size() != cardIds.size()) {
				throw new BusinessException(LinkErrorCode.CARD_NOT_FOUND);
			}
			linkedCards = (int) cards.stream().filter(Card::link).count();
		}

		return new LinkAssetsResponse(linkedAccounts, linkedCards);
	}

	@Transactional
	public void unlinkAccount(long userId, long accountId) {
		Account account = accountRepository.findByIdAndUserId(accountId, userId)
				.orElseThrow(() -> new BusinessException(LinkErrorCode.ACCOUNT_NOT_FOUND));
		account.unlink();
	}

	@Transactional
	public void unlinkCard(long userId, long cardId) {
		Card card = cardRepository.findByIdAndUserId(cardId, userId)
				.orElseThrow(() -> new BusinessException(LinkErrorCode.CARD_NOT_FOUND));
		card.unlink();
	}
}
