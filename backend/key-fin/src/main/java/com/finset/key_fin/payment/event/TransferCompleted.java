package com.finset.key_fin.payment.event;

import com.finset.key_fin.payment.entity.TransferStatus;

public record TransferCompleted(long userId, long transferId, TransferStatus status) {
}
