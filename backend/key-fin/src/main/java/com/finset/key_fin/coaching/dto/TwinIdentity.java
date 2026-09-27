package com.finset.key_fin.coaching.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/** `POST /v1/twin` 응답. 이후 이벤트 전송에 쓰는 revision 을 포함한다. */
@JsonIgnoreProperties(ignoreUnknown = true)
public record TwinIdentity(
		@JsonProperty("user_id") String userId,
		@JsonProperty("twin_id") String twinId,
		@JsonProperty("revision") long revision,
		@JsonProperty("input_digest") String inputDigest,
		@JsonProperty("as_of") String asOf
) {
}
