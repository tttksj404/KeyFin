package com.finset.key_fin.coaching.controller;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.core.MethodParameter;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;

import com.finset.key_fin.coaching.exception.CoachingErrorCode;
import com.finset.key_fin.coaching.service.CoachingChatService;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.exception.GlobalExceptionHandler;

import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class CoachingChartHtmlControllerTest {

	private static final long USER_ID = 970L;
	private static final String HTML = "<!doctype html><html><body>chart</body></html>";

	private final CoachingChatService service = mock(CoachingChatService.class);
	private MockMvc mvc;

	@BeforeEach
	void setUp() {
		mvc = MockMvcBuilders.standaloneSetup(new CoachingChatController(service))
				.setControllerAdvice(new GlobalExceptionHandler())
				.setCustomArgumentResolvers(principal(USER_ID))
				.build();
	}

	@Test
	void 차트_HTML은_봉투_없이_text_html_본문으로_내려준다() throws Exception {
		given(service.chartHtml(USER_ID, "8f1c2d3e")).willReturn(HTML);

		mvc.perform(get("/api/v1/coaching/charts/8f1c2d3e/html"))
				.andExpect(status().isOk())
				.andExpect(content().contentTypeCompatibleWith("text/html"))
				.andExpect(content().string(HTML));
	}

	@Test
	void 없는_차트는_404_AI_002다() throws Exception {
		given(service.chartHtml(USER_ID, "missing"))
				.willThrow(new BusinessException(CoachingErrorCode.CHART_NOT_FOUND));

		mvc.perform(get("/api/v1/coaching/charts/missing/html"))
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.code").value("AI_002"));
	}

	@Test
	void 코칭_서버_장애는_503_AI_001이다() throws Exception {
		given(service.chartHtml(USER_ID, "8f1c2d3e"))
				.willThrow(new BusinessException(CoachingErrorCode.COACHING_UNAVAILABLE));

		mvc.perform(get("/api/v1/coaching/charts/8f1c2d3e/html"))
				.andExpect(status().isServiceUnavailable())
				.andExpect(jsonPath("$.code").value("AI_001"));
	}

	private static HandlerMethodArgumentResolver principal(long userId) {
		return new HandlerMethodArgumentResolver() {
			@Override
			public boolean supportsParameter(MethodParameter parameter) {
				return parameter.getParameterType() == Long.class;
			}

			@Override
			public Object resolveArgument(MethodParameter parameter, ModelAndViewContainer mavContainer,
					NativeWebRequest webRequest, WebDataBinderFactory binderFactory) {
				return userId;
			}
		};
	}
}
