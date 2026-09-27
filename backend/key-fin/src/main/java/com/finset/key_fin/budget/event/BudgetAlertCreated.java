package com.finset.key_fin.budget.event;

import com.finset.key_fin.budget.entity.BudgetAlertLevel;

/** 봉투 잔액 구간이 나빠져 알림을 만든 직후 발행한다. 복구 알림에는 발행하지 않는다. */
public record BudgetAlertCreated(
		long userId,
		int envelopeId,
		String envelopeName,
		long notificationId,
		BudgetAlertLevel level
) {
}
