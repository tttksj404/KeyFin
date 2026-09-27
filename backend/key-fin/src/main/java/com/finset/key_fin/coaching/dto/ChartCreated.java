package com.finset.key_fin.coaching.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/** `POST /v1/charts/budget-forecast` 응답 중 앱에 넘기는 id 만 읽는다. */
@JsonIgnoreProperties(ignoreUnknown = true)
public record ChartCreated(@JsonProperty("id") String id) {
}
