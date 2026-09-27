package com.finset.key_fin.transaction.scheduler;

import com.finset.key_fin.transaction.service.TransactionSyncManager;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.repository.UserRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalDateTime;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class TransactionSyncSchedulerTest {

	@Mock
	private UserRepository userRepository;
	@Mock
	private TransactionSyncManager syncManager;

	@Test
	void 금융_연결된_활성_사용자를_한명씩_동기화한다() {
		TransactionSyncScheduler scheduler = scheduler();
		User first = user(1L);
		User second = user(2L);
		given(userRepository.findAllByFinUserKeyIsNotNullAndDeletedAtIsNull())
				.willReturn(List.of(first, second));

		scheduler.syncAll();

		verify(syncManager).syncUser(eq(1L), any(LocalDateTime.class));
		verify(syncManager).syncUser(eq(2L), any(LocalDateTime.class));
	}

	@Test
	void 사용자_한명의_동기화이_실패해도_다음_사용자를_계속한다() {
		TransactionSyncScheduler scheduler = scheduler();
		User first = user(1L);
		User second = user(2L);
		given(userRepository.findAllByFinUserKeyIsNotNullAndDeletedAtIsNull())
				.willReturn(List.of(first, second));
		doThrow(new IllegalStateException("boom"))
				.when(syncManager).syncUser(eq(1L), any(LocalDateTime.class));

		scheduler.syncAll();

		verify(syncManager).syncUser(eq(2L), any(LocalDateTime.class));
	}

	@Test
	void 이전_동기화이_실행_중이면_새로운_실행을_건너뛴다() {
		TransactionSyncScheduler scheduler = scheduler();
		AtomicBoolean running = (AtomicBoolean) ReflectionTestUtils.getField(scheduler, "running");
		assertThat(running).isNotNull();
		running.set(true);

		scheduler.syncAll();

		verifyNoInteractions(userRepository, syncManager);
	}

	@Test
	void 실행_중_오류가_발생해도_다음_실행이_가능하다() {
		TransactionSyncScheduler scheduler = scheduler();
		given(userRepository.findAllByFinUserKeyIsNotNullAndDeletedAtIsNull())
				.willThrow(new IllegalStateException("boom"))
				.willReturn(List.of());

		assertThatThrownBy(scheduler::syncAll)
				.isInstanceOf(IllegalStateException.class);
		scheduler.syncAll();

		verify(userRepository, times(2)).findAllByFinUserKeyIsNotNullAndDeletedAtIsNull();
		verify(syncManager, never()).syncUser(any(Long.class), any(LocalDateTime.class));
	}

	private TransactionSyncScheduler scheduler() {
		return new TransactionSyncScheduler(userRepository, syncManager);
	}

	private User user(long id) {
		User user = org.mockito.Mockito.mock(User.class);
		given(user.getId()).willReturn(id);
		return user;
	}
}

