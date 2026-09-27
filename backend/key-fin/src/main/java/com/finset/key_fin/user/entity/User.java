package com.finset.key_fin.user.entity;

import com.finset.key_fin.global.base.BaseEntity;
import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.user.exception.UserErrorCode;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.Objects;

@Getter
@Entity
@Table(name = "users")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class User extends BaseEntity {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@Column(nullable = false, unique = true, length = 100)
	private String email;

	@Column(nullable = false, length = 255)
	private String password;

	@Column(nullable = false, length = 30)
	private String name;

	@Column(name = "fin_user_key", unique = true, length = 60)
	private String finUserKey;

	@Column(name = "deleted_at")
	private LocalDateTime deletedAt;

	private User(String email, String password, String name) {
		this.email = Objects.requireNonNull(email, "email must not be null");
		this.password = Objects.requireNonNull(password, "password must not be null");
		this.name = Objects.requireNonNull(name, "name must not be null");
	}

	public static User create(String email, String password, String name) {
		return new User(email, password, name);
	}

	public void connectFinance(String finUserKey) {
		String validatedFinUserKey = validateFinUserKey(finUserKey);
		if (isFinanceConnected()) {
			if (this.finUserKey.equals(validatedFinUserKey)) {
				return;
			}
			throw new BusinessException(UserErrorCode.FINANCE_CONNECTION_CONFLICT);
		}

		this.finUserKey = validatedFinUserKey;
	}

	public boolean isFinanceConnected() {
		return finUserKey != null;
	}

	public boolean isDeleted() {
		return deletedAt != null;
	}

	public void softDelete(LocalDateTime deletedAt) {
		if (isDeleted()) {
			throw new BusinessException(UserErrorCode.DELETED_USER);
		}
		this.deletedAt = Objects.requireNonNull(deletedAt, "deletedAt must not be null");
	}

	private String validateFinUserKey(String finUserKey) {
		if (finUserKey == null || finUserKey.isBlank()) {
			throw new IllegalArgumentException("금융망 사용자 키는 비어 있을 수 없습니다.");
		}
		if (finUserKey.length() > 60) {
			throw new IllegalArgumentException("금융망 사용자 키는 60자를 초과할 수 없습니다.");
		}
		return finUserKey;
	}
}
