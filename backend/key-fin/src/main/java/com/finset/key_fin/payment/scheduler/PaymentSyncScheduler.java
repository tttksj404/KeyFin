package com.finset.key_fin.payment.scheduler;

import java.util.List;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import com.finset.key_fin.payment.service.CardBillingSyncService;
import com.finset.key_fin.payment.service.SubscriptionSyncService;
import com.finset.key_fin.payment.service.TransferProposalService;
import com.finset.key_fin.payment.service.TransferService;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Slf4j
@Component
@RequiredArgsConstructor
public class PaymentSyncScheduler {

	private final UserRepository userRepository;
	private final SubscriptionSyncService subscriptionSyncService;
	private final CardBillingSyncService cardBillingSyncService;
	private final TransferProposalService transferProposalService;
	private final TransferService transferService;

	/** 08:00 — 월요일 07:30 청구서 발행 직후. 17:00 — 출금 요일 16:00 출금 결과 반영. */
	@Scheduled(cron = "${payment.sync.cron}", zone = "Asia/Seoul")
	public void syncAll() {
		List<User> users = userRepository.findAllByFinUserKeyIsNotNullAndDeletedAtIsNull();
		int failed = 0;
		for (User user : users) {
			if (!syncOne(user.getId())) {
				failed++;
			}
		}
		log.info("결제 동기화 완료: users={}, failed={}", users.size(), failed);
	}

	/** 08:30 — 동기화 직후 오늘·내일 출금 중 부족한 건에 이체를 제안한다. */
	@Scheduled(cron = "${payment.transfer-proposal.cron}", zone = "Asia/Seoul")
	public void proposeAll() {
		List<User> users = userRepository.findAllByFinUserKeyIsNotNullAndDeletedAtIsNull();
		int failed = 0;
		for (User user : users) {
			try {
				transferProposalService.propose(user.getId());
			} catch (RuntimeException e) {
				failed++;
				log.warn("이체 제안 실패 — 다음 사용자로: userId={}, cause={}", user.getId(), e.toString());
			}
		}
		log.info("이체 제안 완료: users={}, failed={}", users.size(), failed);
	}

	/** 30분 — 승인 후 금융망 응답을 못 받아 APPROVED로 남은 건을 같은 번호로 재전송한다. */
	@Scheduled(cron = "${payment.transfer-recover.cron}", zone = "Asia/Seoul")
	public void recoverApproved() {
		transferService.recoverApproved();
	}

	boolean syncOne(long userId) {
		try {
			subscriptionSyncService.sync(userId);
			cardBillingSyncService.sync(userId);
			return true;
		} catch (RuntimeException e) {
			log.warn("결제 동기화 실패 — 다음 사용자로: userId={}, cause={}", userId, e.toString());
			return false;
		}
	}
}
