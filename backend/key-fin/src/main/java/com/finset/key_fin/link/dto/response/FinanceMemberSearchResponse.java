package com.finset.key_fin.link.dto.response;

import com.fasterxml.jackson.annotation.JsonAlias;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record FinanceMemberSearchResponse(
		String userId,
		@JsonAlias("username") String userName,
		String institutionCode,
		String userKey,
		String created,
		String modified
) {

	@Override
	public String toString() {
		return "FinanceMemberSearchResponse[userId=" + userId
				+ ", userName=" + userName
				+ ", institutionCode=" + institutionCode
				+ ", userKey=******"
				+ ", created=" + created
				+ ", modified=" + modified + "]";
	}
}
