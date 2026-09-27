package com.finset.key_fin.payment.controller;

import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.springframework.test.web.servlet.setup.MockMvcBuilders.standaloneSetup;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.method.annotation.AuthenticationPrincipalArgumentResolver;
import org.springframework.test.web.servlet.MockMvc;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.exception.GlobalExceptionHandler;
import com.finset.key_fin.payment.dto.response.PaymentCalendarResponse.CalendarItemType;
import com.finset.key_fin.payment.dto.response.TransferApproveResponse;
import com.finset.key_fin.payment.dto.response.TransferDetailResponse;
import com.finset.key_fin.payment.dto.response.TransferDetailResponse.HistoryEntry;
import com.finset.key_fin.payment.entity.AuditLog.AuditAction;
import com.finset.key_fin.payment.dto.response.TransferListResponse;
import com.finset.key_fin.payment.dto.response.TransferResponse;
import com.finset.key_fin.payment.dto.response.TransferResponse.Purpose;
import com.finset.key_fin.payment.entity.TransferStatus;
import com.finset.key_fin.payment.exception.PaymentErrorCode;
import com.finset.key_fin.payment.service.TransferService;

class TransferControllerTest {

	private TransferService transferService;
	private MockMvc mockMvc;

	@BeforeEach
	void setUp() {
		transferService = mock(TransferService.class);
		mockMvc = standaloneSetup(new TransferController(transferService))
				.setControllerAdvice(new GlobalExceptionHandler())
				.setCustomArgumentResolvers(new AuthenticationPrincipalArgumentResolver())
				.build();
		SecurityContextHolder.getContext().setAuthentication(
				UsernamePasswordAuthenticationToken.authenticated(1L, null, List.of()));
	}

	@AfterEach
	void tearDown() {
		SecurityContextHolder.clearContext();
	}

	@Test
	void listsProposedTransfers() throws Exception {
		when(transferService.list(1L, TransferStatus.PROPOSED, null, null, null)).thenReturn(new TransferListResponse(
				List.of(new TransferResponse(
						21L, TransferStatus.PROPOSED, LocalDate.of(2026, 9, 14), LocalDate.of(2026, 9, 15), 230000L, 1L, 3L,
						new Purpose(CalendarItemType.FIXED, 7L, null, "월세"), null, null, LocalDateTime.of(2026, 9, 14, 8, 30))),
				null));

		mockMvc.perform(get("/api/v1/transfers").param("status", "PROPOSED"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.items[0].id").value(21))
				.andExpect(jsonPath("$.data.items[0].status").value("PROPOSED"))
				.andExpect(jsonPath("$.data.items[0].dueDate").value("2026-09-15"))
				.andExpect(jsonPath("$.data.items[0].purpose.type").value("FIXED"))
				.andExpect(jsonPath("$.data.items[0].purpose.name").value("월세"))
				.andExpect(jsonPath("$.data.nextCursor").doesNotExist());
	}

	@Test
	void forwardsPagingParamsAndReturnsNextCursor() throws Exception {
		when(transferService.list(1L, TransferStatus.EXECUTED, "202609", 9905L, 3))
				.thenReturn(new TransferListResponse(List.of(), 9902L));

		mockMvc.perform(get("/api/v1/transfers")
						.param("status", "EXECUTED").param("month", "202609").param("cursor", "9905").param("size", "3"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.items").isEmpty())
				.andExpect(jsonPath("$.data.nextCursor").value(9902));
	}

	@Test
	void returnsDetailWithHistory() throws Exception {
		when(transferService.detail(1L, 21L)).thenReturn(new TransferDetailResponse(
				new TransferResponse(21L, TransferStatus.EXECUTED, LocalDate.of(2026, 9, 14), LocalDate.of(2026, 9, 15), 230000L, 1L, 3L,
						new Purpose(CalendarItemType.FIXED, 7L, null, "월세"), LocalDateTime.of(2026, 9, 14, 9, 12), null,
						LocalDateTime.of(2026, 9, 14, 8, 30)),
				List.of(new HistoryEntry(AuditAction.EXECUTE, "금융망 H0000", LocalDateTime.of(2026, 9, 14, 9, 12)))));

		mockMvc.perform(get("/api/v1/transfers/21"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.transfer.id").value(21))
				.andExpect(jsonPath("$.data.transfer.status").value("EXECUTED"))
				.andExpect(jsonPath("$.data.history[0].action").value("EXECUTE"))
				.andExpect(jsonPath("$.data.history[0].at").value("2026-09-14T09:12:00"));
	}

	@Test
	void detailOfOthersIs404() throws Exception {
		doThrow(new BusinessException(PaymentErrorCode.TRANSFER_NOT_FOUND)).when(transferService).detail(1L, 99L);

		mockMvc.perform(get("/api/v1/transfers/99"))
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.code").value("PAY_005"));
	}

	@Test
	void listsAllWhenStatusOmitted() throws Exception {
		when(transferService.list(1L, null, null, null, null)).thenReturn(new TransferListResponse(List.of(), null));

		mockMvc.perform(get("/api/v1/transfers"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.items").isEmpty());
		verify(transferService).list(eq(1L), isNull(), isNull(), isNull(), isNull());
	}

	@Test
	void approvesTransfer() throws Exception {
		when(transferService.approve(1L, 21L)).thenReturn(
				new TransferApproveResponse(21L, TransferStatus.EXECUTED, LocalDateTime.of(2026, 9, 14, 8, 31), null));

		mockMvc.perform(post("/api/v1/transfers/21/approve"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.status").value("EXECUTED"))
				.andExpect(jsonPath("$.data.executedAt").value("2026-09-14T08:31:00"));
	}

	@Test
	void mapsSafeguardRejectionTo403() throws Exception {
		when(transferService.approve(1L, 21L)).thenThrow(new BusinessException(PaymentErrorCode.TRANSFER_CONSENT_OFF));

		mockMvc.perform(post("/api/v1/transfers/21/approve"))
				.andExpect(status().isForbidden())
				.andExpect(jsonPath("$.code").value("PAY_007"));
	}

	@Test
	void postponesTransfer() throws Exception {
		mockMvc.perform(post("/api/v1/transfers/21/postpone"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.success").value(true));
		verify(transferService).postpone(1L, 21L);

		doThrow(new BusinessException(PaymentErrorCode.TRANSFER_NOT_PROPOSED)).when(transferService).postpone(1L, 22L);
		mockMvc.perform(post("/api/v1/transfers/22/postpone"))
				.andExpect(status().isConflict())
				.andExpect(jsonPath("$.code").value("PAY_006"));
	}
}
