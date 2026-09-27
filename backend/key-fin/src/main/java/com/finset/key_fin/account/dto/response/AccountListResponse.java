package com.finset.key_fin.account.dto.response;

import com.finset.key_fin.account.entity.Account;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.LocalDateTime;
import java.util.List;

import static io.swagger.v3.oas.annotations.media.Schema.RequiredMode.REQUIRED;

@Schema(description = "연결 계좌 목록")
public record AccountListResponse(
		@Schema(description = "관리 중인 계좌 목록", requiredMode = REQUIRED)
		List<AccountItem> items
) {

	public static AccountListResponse from(List<Account> accounts) {
		return new AccountListResponse(accounts.stream().map(AccountItem::from).toList());
	}

	public record AccountItem(
			@Schema(description = "계좌 ID", example = "3", requiredMode = REQUIRED)
			Long id,
			@Schema(description = "금융계좌번호", example = "0010011073486799", requiredMode = REQUIRED)
			String finAccountNo,
			@Schema(description = "은행명", example = "한국은행", requiredMode = REQUIRED)
			String bankName,
			@Schema(description = "계좌 별칭", example = "생활비", nullable = true)
			String alias,
			@Schema(description = "수입 계좌 여부", example = "true", requiredMode = REQUIRED)
			boolean isIncome,
			@Schema(description = "관리 대상 여부", example = "true", requiredMode = REQUIRED)
			boolean isManaged,
			@Schema(description = "마지막으로 갱신된 잔액", example = "1500000", requiredMode = REQUIRED)
			long balance,
			@Schema(description = "잔액 업데이트 시각", example = "2026-09-11T14:30:00", requiredMode = REQUIRED)
			LocalDateTime balanceUpdatedAt
	) {

		public static AccountItem from(Account account) {
			return new AccountItem(
					account.getId(),
					account.getFinAccountNo(),
					account.getBankName(),
					account.getAlias(),
					account.isIncome(),
					account.isManaged(),
					account.getBalance(),
					account.getBalanceUpdatedAt()
			);
		}
	}
}
