package com.finset.key_fin.fincoin.service;

import com.finset.key_fin.fincoin.dto.response.AttendanceCheckResponse;
import com.finset.key_fin.fincoin.entity.FinCoin;
import com.finset.key_fin.fincoin.entity.FinCoinReason;
import com.finset.key_fin.fincoin.repository.FinCoinRepository;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.mockito.InOrder;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class AttendanceServiceTest {

	private static final long USER_ID = 1L;
	private static final LocalDate TODAY = LocalDate.of(2026, 9, 12);
	private final User user = User.create("attendance@test.io", "encoded", "출석테스터");
	private UserRepository users;
	private FinCoinRepository coins;
	private FinCoinService service;

	@BeforeEach
	void setUp() {
		users = mock(UserRepository.class);
		coins = mock(FinCoinRepository.class);
		service = new FinCoinServiceImpl(coins, users,
				Clock.fixed(Instant.parse("2026-09-11T15:00:00Z"), ZoneOffset.UTC));
		when(users.findActiveByIdForUpdate(USER_ID)).thenReturn(Optional.of(user));
	}

	@Test
	void grantsTenCoinsUsingKoreanDateAndLatestLedgerBalance() {
		when(coins.findFirstByUserIdOrderByIdDesc(USER_ID))
				.thenReturn(Optional.of(FinCoin.forAttendance(user, TODAY.minusDays(1), 1250, 0)));

		assertThat(service.checkAttendance(USER_ID)).isEqualTo(new AttendanceCheckResponse(10, 1260));

		ArgumentCaptor<FinCoin> saved = ArgumentCaptor.forClass(FinCoin.class);
		verify(coins).save(saved.capture());
		FinCoin coin = saved.getValue();
		assertThat(coin.getUser()).isSameAs(user);
		assertThat(coin.getGrantDate()).isEqualTo(TODAY);
		assertThat(coin.getReasonCode()).isEqualTo(FinCoinReason.ATTEND);
		assertThat(coin.getDelta()).isEqualTo(10);
		assertThat(coin.getBalanceAfter()).isEqualTo(1260);
		assertThat(coin.getRefId()).isNull();
	}

	@Test
	void locksUserBeforeCalculatingDateOrReadingLedger() {
		Clock clock = mock(Clock.class);
		when(clock.withZone(ZoneId.of("Asia/Seoul")))
				.thenReturn(Clock.fixed(Instant.parse("2026-09-11T15:00:00Z"), ZoneId.of("Asia/Seoul")));
		service = new FinCoinServiceImpl(coins, users, clock);

		assertThat(service.checkAttendance(USER_ID)).isEqualTo(new AttendanceCheckResponse(10, 10));

		InOrder order = inOrder(users, clock, coins);
		order.verify(users).findActiveByIdForUpdate(USER_ID);
		order.verify(clock).withZone(ZoneId.of("Asia/Seoul"));
		order.verify(coins).existsByUserIdAndGrantDateAndReasonCode(USER_ID, TODAY, FinCoinReason.ATTEND);
		order.verify(coins).findFirstByUserIdOrderByIdDesc(USER_ID);
		order.verify(coins).save(any(FinCoin.class));
	}

	@Test
	void returnsCurrentBalanceWithoutSavingOnDuplicate() {
		when(coins.existsByUserIdAndGrantDateAndReasonCode(USER_ID, TODAY, FinCoinReason.ATTEND)).thenReturn(true);
		when(coins.findFirstByUserIdOrderByIdDesc(USER_ID))
				.thenReturn(Optional.of(FinCoin.forAttendance(user, TODAY, 50, 0)));

		assertThat(service.checkAttendance(USER_ID)).isEqualTo(new AttendanceCheckResponse(0, 50));
		verify(coins, never()).save(any());
	}

	@Test
	void rejectsInactiveUserBeforeReadingOrWritingCoins() {
		when(users.findActiveByIdForUpdate(USER_ID)).thenReturn(Optional.empty());

		assertThatThrownBy(() -> service.checkAttendance(USER_ID))
				.isInstanceOfSatisfying(BusinessException.class,
						error -> assertThat(error.getErrorCode()).isEqualTo(UserErrorCode.USER_NOT_FOUND));
		verifyNoInteractions(coins);
	}

	@Test
	void propagatesStorageFailureInsteadOfReportingSuccess() {
		RuntimeException failure = new IllegalStateException("storage unavailable");
		doThrow(failure).when(coins).save(any(FinCoin.class));

		assertThatThrownBy(() -> service.checkAttendance(USER_ID)).isSameAs(failure);
	}

	@Test
	void doesNotWriteWhenBalanceWouldOverflow() {
		when(coins.findFirstByUserIdOrderByIdDesc(USER_ID))
				.thenReturn(Optional.of(FinCoin.forAttendance(user, TODAY.minusDays(1), Integer.MAX_VALUE, 0)));

		assertThatThrownBy(() -> service.checkAttendance(USER_ID)).isInstanceOf(ArithmeticException.class);
		verify(coins, never()).save(any());
	}
}
