package com.finset.key_fin.auth.repository;

public interface RefreshTokenRepository {

	void save(long userId, String refreshToken);

	boolean matches(long userId, String refreshToken);

	void delete(long userId);
}
