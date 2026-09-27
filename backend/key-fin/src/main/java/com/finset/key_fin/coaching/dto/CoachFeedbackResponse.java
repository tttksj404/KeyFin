package com.finset.key_fin.coaching.dto;

public record CoachFeedbackResponse(Status status, String text) {

	public enum Status { PENDING, READY, FAILED, NONE }

	public static CoachFeedbackResponse none() {
		return new CoachFeedbackResponse(Status.NONE, null);
	}
}
