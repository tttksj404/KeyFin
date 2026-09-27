package com.finset.key_fin.fincoin.service;

import com.finset.key_fin.fincoin.dto.response.AttendanceCheckResponse;
import com.finset.key_fin.fincoin.dto.response.FinCoinBalanceResponse;
import com.finset.key_fin.fincoin.dto.response.FinCoinResponse;

public interface FinCoinService {

	FinCoinResponse getFinCoins(long userId, Long cursor, int size);

	FinCoinBalanceResponse getFinCoinBalance(long userId);

	AttendanceCheckResponse checkAttendance(long userId);
}
