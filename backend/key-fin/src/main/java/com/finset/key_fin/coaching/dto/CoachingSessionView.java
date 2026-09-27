package com.finset.key_fin.coaching.dto;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public record CoachingSessionView(
		@JsonProperty("id") String id,
		@JsonProperty("expires_at") double expiresAt,
		@JsonProperty("messages") List<Message> messages
) {
	@JsonIgnoreProperties(ignoreUnknown = true)
	public record Message(
			@JsonProperty("role") String role,
			@JsonProperty("content") String content,
			@JsonProperty("response") AnswerReference response
	) {
	}

	@JsonIgnoreProperties(ignoreUnknown = true)
	public record AnswerReference(
			@JsonProperty("kind") String kind,
			@JsonProperty("id") String id
	) {
	}
}
