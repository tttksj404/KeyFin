package com.finset.key_fin.budget.dto.response;

import com.finset.key_fin.budget.dto.response.BudgetCurrentResponse.Emergency;

public record EmergencyFundResponse(Long budgetId, Emergency emergency) {
}
