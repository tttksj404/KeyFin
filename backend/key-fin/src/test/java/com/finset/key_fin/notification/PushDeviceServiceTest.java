package com.finset.key_fin.notification;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.notification.dto.request.PushDeviceRequest;
import com.finset.key_fin.notification.repository.PushDeviceRepository;
import com.finset.key_fin.notification.service.PushDeviceService;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.dao.CannotAcquireLockException;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.SimpleTransactionStatus;
import java.time.Clock;
import java.util.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.assertj.core.api.Assertions.*;

class PushDeviceServiceTest {
    @Test void retriesInFreshTransactionsAndCommitsThirdAttempt() {
        var repository = mock(PushDeviceRepository.class);
        var manager = mock(PlatformTransactionManager.class);
        when(manager.getTransaction(any())).thenAnswer(call -> {
            assertThat(call.<TransactionDefinition>getArgument(0).getPropagationBehavior())
                    .isEqualTo(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
            return new SimpleTransactionStatus();
        });
        when(repository.isActiveUser(1)).thenReturn(true);
        when(repository.lockRegistration(anyString(), anyString()))
                .thenThrow(new DuplicateKeyException("sensitive-token"))
                .thenThrow(new CannotAcquireLockException("deadlock"))
                .thenReturn(List.of());
        new PushDeviceService(repository, Clock.systemUTC(), manager)
                .register(1, UUID.randomUUID(), new PushDeviceRequest("token", "ANDROID"));
        verify(manager, times(3)).getTransaction(any());
        verify(manager, times(2)).rollback(any());
        verify(manager).commit(any());
    }

    @Test void exhaustedConflictIsSanitized() {
        var repository = mock(PushDeviceRepository.class);
        var manager = mock(PlatformTransactionManager.class);
        when(manager.getTransaction(any())).thenAnswer(call -> new SimpleTransactionStatus());
        when(repository.isActiveUser(1)).thenReturn(true);
        when(repository.lockRegistration(anyString(), anyString())).thenThrow(new DuplicateKeyException("secret-token"));
        var service = new PushDeviceService(repository, Clock.systemUTC(), manager);
        assertThatThrownBy(() -> service.register(1, UUID.randomUUID(), new PushDeviceRequest("token", "ANDROID")))
                .isInstanceOfSatisfying(BusinessException.class, error -> {
                    assertThat(error.getErrorCode().getCode()).isEqualTo("PUSH_001");
                    assertThat(error.getMessage()).doesNotContain("secret-token");
                    assertThat(error.getCause()).isNull();
                });
        verify(manager, times(3)).rollback(any());
    }
}
