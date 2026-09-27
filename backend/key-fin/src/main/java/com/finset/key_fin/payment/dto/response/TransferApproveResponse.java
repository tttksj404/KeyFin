package com.finset.key_fin.payment.dto.response;

import java.time.LocalDateTime;
import com.finset.key_fin.payment.entity.TransferStatus;

public record TransferApproveResponse(Long id, TransferStatus status, LocalDateTime executedAt, String failReason) {
}
