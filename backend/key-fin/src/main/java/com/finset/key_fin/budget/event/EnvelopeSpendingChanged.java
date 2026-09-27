package com.finset.key_fin.budget.event;

/** restoredKrw 는 결제 취소로 봉투에 되돌아온 금액. 취소가 아닌 변경은 null 이다. */
public record EnvelopeSpendingChanged(long userId, int envelopeId, Long restoredKrw) {

	public EnvelopeSpendingChanged(long userId, int envelopeId) {
		this(userId, envelopeId, null);
	}
}
