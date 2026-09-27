package com.finset.key_fin.link.controller;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.exception.GlobalExceptionHandler;
import com.finset.key_fin.link.dto.request.FinanceConnectRequest;
import com.finset.key_fin.link.dto.request.LinkAssetsRequest;
import com.finset.key_fin.link.dto.response.FinanceConnectResponse;
import com.finset.key_fin.link.dto.response.LinkAssetsResponse;
import com.finset.key_fin.link.dto.response.LinkCandidatesResponse;
import com.finset.key_fin.link.exception.LinkErrorCode;
import com.finset.key_fin.link.service.FinanceConnectService;
import com.finset.key_fin.link.service.AssetLinkService;
import com.finset.key_fin.link.service.LinkCandidateService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.method.annotation.AuthenticationPrincipalArgumentResolver;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.springframework.test.web.servlet.setup.MockMvcBuilders.standaloneSetup;

class LinkControllerTest {

	private static final long USER_ID = 1L;

	private FinanceConnectService financeConnectService;
	private LinkCandidateService linkCandidateService;
	private AssetLinkService assetLinkService;
	private MockMvc mockMvc;

	@BeforeEach
	void setUp() {
		financeConnectService = mock(FinanceConnectService.class);
		linkCandidateService = mock(LinkCandidateService.class);
		assetLinkService = mock(AssetLinkService.class);
		mockMvc = standaloneSetup(new LinkController(financeConnectService, linkCandidateService, assetLinkService))
				.setControllerAdvice(new GlobalExceptionHandler())
				.setCustomArgumentResolvers(new AuthenticationPrincipalArgumentResolver())
				.build();
		SecurityContextHolder.getContext().setAuthentication(
				UsernamePasswordAuthenticationToken.authenticated(USER_ID, null, List.of())
		);
	}

	@AfterEach
	void tearDown() {
		SecurityContextHolder.clearContext();
	}

	@Test
	void 입력한_금융망_이메일로_회원을_연결한다() throws Exception {
		FinanceConnectRequest request = new FinanceConnectRequest("finance@qwer.com");
		when(financeConnectService.connect(USER_ID, request))
				.thenReturn(FinanceConnectResponse.of(true));

		mockMvc.perform(post("/api/v1/links/connect")
						.contentType(MediaType.APPLICATION_JSON)
						.content("""
								{"financeEmail":"finance@qwer.com"}
								"""))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.success").value(true))
				.andExpect(jsonPath("$.data.connected").value(true));

		verify(financeConnectService).connect(USER_ID, request);
	}

	@Test
	void 올바르지_않은_금융망_이메일을_거절한다() throws Exception {
		mockMvc.perform(post("/api/v1/links/connect")
						.contentType(MediaType.APPLICATION_JSON)
						.content("""
								{"financeEmail":"invalid-email"}
								"""))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.success").value(false))
				.andExpect(jsonPath("$.code").value("COMMON_001"));
	}

	@Test
	void 금융망_연결_상태를_조회한다() throws Exception {
		when(financeConnectService.getStatus(USER_ID)).thenReturn(FinanceConnectResponse.of(false));

		mockMvc.perform(get("/api/v1/links/status"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.success").value(true))
				.andExpect(jsonPath("$.data.connected").value(false));

		verify(financeConnectService).getStatus(USER_ID);
	}

	@Test
	void 계좌_카드_후보_목록을_조회한다() throws Exception {
		when(linkCandidateService.getCandidates(USER_ID)).thenReturn(new LinkCandidatesResponse(
				List.of(new LinkCandidatesResponse.AccountCandidate(3L, "0010011073486799", "001", "한국은행", 1_500_000L, false)),
				List.of(new LinkCandidatesResponse.CardCandidate(7L, "1003198565339181", "롯데카드", "디지로카 SEOUL", "0323555042323510", true))
		));

		mockMvc.perform(get("/api/v1/links/candidates"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.success").value(true))
				.andExpect(jsonPath("$.data.accounts[0].id").value(3))
				.andExpect(jsonPath("$.data.accounts[0].finAccountNo").value("0010011073486799"))
				.andExpect(jsonPath("$.data.accounts[0].bankName").value("한국은행"))
				.andExpect(jsonPath("$.data.accounts[0].balance").value(1_500_000))
				.andExpect(jsonPath("$.data.accounts[0].managed").value(false))
				.andExpect(jsonPath("$.data.cards[0].id").value(7))
				.andExpect(jsonPath("$.data.cards[0].cardNo").value("1003198565339181"))
				.andExpect(jsonPath("$.data.cards[0].issuerName").value("롯데카드"))
				.andExpect(jsonPath("$.data.cards[0].managed").value(true));

		verify(linkCandidateService).getCandidates(USER_ID);
	}

	@Test
	void 선택한_계좌와_카드를_연결하고_201을_반환한다() throws Exception {
		LinkAssetsRequest request = new LinkAssetsRequest(List.of(3L), List.of(7L));
		when(assetLinkService.link(USER_ID, request)).thenReturn(new LinkAssetsResponse(1, 1));

		mockMvc.perform(post("/api/v1/links")
						.contentType(MediaType.APPLICATION_JSON)
						.content("""
								{"accountIds":[3],"cardIds":[7]}
								"""))
				.andExpect(status().isCreated())
				.andExpect(jsonPath("$.success").value(true))
				.andExpect(jsonPath("$.data.accounts").value(1))
				.andExpect(jsonPath("$.data.cards").value(1));

		verify(assetLinkService).link(USER_ID, request);
	}

	@Test
	void 양수가_아닌_계좌_ID는_400으로_거절한다() throws Exception {
		mockMvc.perform(post("/api/v1/links")
						.contentType(MediaType.APPLICATION_JSON)
						.content("""
								{"accountIds":[0],"cardIds":[]}
								"""))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("COMMON_001"));
	}

	@Test
	void 본인_소유가_아닌_계좌_ID_연결은_404로_거절한다() throws Exception {
		when(assetLinkService.link(eq(USER_ID), any(LinkAssetsRequest.class)))
				.thenThrow(new BusinessException(LinkErrorCode.ACCOUNT_NOT_FOUND));

		mockMvc.perform(post("/api/v1/links")
						.contentType(MediaType.APPLICATION_JSON)
						.content("""
								{"accountIds":[999]}
								"""))
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.code").value("LINK_004"));
	}

	@Test
	void 계좌_연결을_해제한다() throws Exception {
		mockMvc.perform(delete("/api/v1/links/accounts/10"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.success").value(true));

		verify(assetLinkService).unlinkAccount(USER_ID, 10L);
	}

	@Test
	void 카드_연결을_해제한다() throws Exception {
		mockMvc.perform(delete("/api/v1/links/cards/20"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.success").value(true));

		verify(assetLinkService).unlinkCard(USER_ID, 20L);
	}

	@Test
	void 본인_카드가_아닌_해제_요청은_404로_거절한다() throws Exception {
		doThrow(new BusinessException(LinkErrorCode.CARD_NOT_FOUND))
				.when(assetLinkService).unlinkCard(USER_ID, 20L);

		mockMvc.perform(delete("/api/v1/links/cards/20"))
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.code").value("LINK_005"));
	}

	@Test
	void 금융망_미연결_사용자의_후보_목록_요청은_409로_거절한다() throws Exception {
		when(linkCandidateService.getCandidates(USER_ID))
				.thenThrow(new BusinessException(LinkErrorCode.FINANCE_NOT_CONNECTED));

		mockMvc.perform(get("/api/v1/links/candidates"))
				.andExpect(status().isConflict())
				.andExpect(jsonPath("$.success").value(false))
				.andExpect(jsonPath("$.code").value("LINK_002"));
	}
}
