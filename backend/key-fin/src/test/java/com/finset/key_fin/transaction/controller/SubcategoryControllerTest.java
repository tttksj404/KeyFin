package com.finset.key_fin.transaction.controller;

import com.finset.key_fin.global.exception.GlobalExceptionHandler;
import com.finset.key_fin.transaction.dto.response.SubcategoryListResponse;
import com.finset.key_fin.transaction.dto.response.SubcategoryListResponse.EnvelopeItem;
import com.finset.key_fin.transaction.dto.response.SubcategoryListResponse.SubcategoryItem;
import com.finset.key_fin.transaction.service.SubcategoryService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.method.annotation.AuthenticationPrincipalArgumentResolver;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.springframework.test.web.servlet.setup.MockMvcBuilders.standaloneSetup;

class SubcategoryControllerTest {

	private static final long USER_ID = 1L;

	private SubcategoryService subcategoryService;
	private MockMvc mockMvc;

	@BeforeEach
	void setUp() {
		subcategoryService = mock(SubcategoryService.class);
		mockMvc = standaloneSetup(new SubcategoryController(subcategoryService))
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
	void 세분류_목록을_봉투별로_조회한다() throws Exception {
		SubcategoryListResponse response = new SubcategoryListResponse(List.of(
				new EnvelopeItem(1, "외식", List.of(
						new SubcategoryItem(101, "음식점"),
						new SubcategoryItem(102, "카페")
				))
		));
		when(subcategoryService.getSubcategories(USER_ID)).thenReturn(response);

		mockMvc.perform(get("/api/v1/subcategories"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.success").value(true))
				.andExpect(jsonPath("$.data.items[0].envelopeId").value(1))
				.andExpect(jsonPath("$.data.items[0].envelopeName").value("외식"))
				.andExpect(jsonPath("$.data.items[0].subcategories[0].id").value(101))
				.andExpect(jsonPath("$.data.items[0].subcategories[1].name").value("카페"));

		verify(subcategoryService).getSubcategories(USER_ID);
	}
}
