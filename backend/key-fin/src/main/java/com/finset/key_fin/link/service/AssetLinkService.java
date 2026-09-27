package com.finset.key_fin.link.service;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.link.dto.request.LinkAssetsRequest;
import com.finset.key_fin.link.dto.response.LinkAssetsResponse;
import com.finset.key_fin.link.exception.LinkErrorCode;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.LinkedHashSet;
import java.util.Set;

@Service
@RequiredArgsConstructor
public class AssetLinkService {

	private final UserRepository userRepository;
	private final AssetLinkWriter assetLinkWriter;

	public LinkAssetsResponse link(long userId, LinkAssetsRequest request) {
		if (request.isEmpty()) {
			throw new BusinessException(LinkErrorCode.EMPTY_LINK_REQUEST);
		}
		requireActiveUser(userId);

		Set<Long> accountIds = new LinkedHashSet<>(request.accountIdsOrEmpty());
		Set<Long> cardIds = new LinkedHashSet<>(request.cardIdsOrEmpty());
		LinkAssetsResponse response = assetLinkWriter.link(userId, accountIds, cardIds);
		// TODO(yr): 새로 관리되는 계좌가 있으면 연결 커밋 후 syncNewlyManagedAccountHistory를 호출한다.
		return response;
	}

	public void unlinkAccount(long userId, long accountId) {
		requireActiveUser(userId);
		assetLinkWriter.unlinkAccount(userId, accountId);
	}

	public void unlinkCard(long userId, long cardId) {
		requireActiveUser(userId);
		assetLinkWriter.unlinkCard(userId, cardId);
	}

	private void requireActiveUser(long userId) {
		userRepository.findByIdAndDeletedAtIsNull(userId)
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_NOT_FOUND));
	}
}
