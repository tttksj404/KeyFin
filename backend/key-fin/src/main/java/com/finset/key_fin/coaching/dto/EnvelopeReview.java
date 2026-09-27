package com.finset.key_fin.coaching.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/** `POST /v1/coaching/envelope-reviews` 응답 중 앱에 보여 줄 문장만 읽는다. */
@JsonIgnoreProperties(ignoreUnknown = true)
public record EnvelopeReview(@JsonProperty("text") String text) {
}
