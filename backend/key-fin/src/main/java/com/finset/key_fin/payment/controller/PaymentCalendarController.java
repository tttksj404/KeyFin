package com.finset.key_fin.payment.controller;

import java.time.Clock;
import java.time.YearMonth;

import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.finset.key_fin.global.base.BaseResponse;
import com.finset.key_fin.payment.dto.response.PaymentCalendarResponse;
import com.finset.key_fin.payment.service.PaymentCalendarService;

import lombok.RequiredArgsConstructor;

@RestController
@RequestMapping("/api/v1/payments")
@RequiredArgsConstructor
public class PaymentCalendarController implements PaymentCalendarControllerDocs {

	private final PaymentCalendarService paymentCalendarService;
	private final Clock clock;

	@GetMapping("/calendar")
	@Override
	public BaseResponse<PaymentCalendarResponse> getCalendar(
			@AuthenticationPrincipal Long userId,
			@RequestParam(required = false) @DateTimeFormat(pattern = "yyyyMM") YearMonth month
	) {
		YearMonth target = month != null ? month : YearMonth.now(clock);
		return BaseResponse.ok(paymentCalendarService.getCalendar(userId, target));
	}
}
