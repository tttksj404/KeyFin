package com.finset.key_fin.user.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.MapsId;
import jakarta.persistence.OneToOne;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.Generated;
import org.hibernate.generator.EventType;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Objects;

@Getter
@Entity
@Table(name = "user_profiles")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class UserProfile {

	@Id
	@Column(name = "user_id")
	private Long userId;

	@MapsId
	@OneToOne(fetch = FetchType.LAZY, optional = false)
	@JoinColumn(name = "user_id", nullable = false)
	private User user;

	@Column(name = "birth_date")
	private LocalDate birthDate;

	@Column(name = "region_code", length = 10)
	private String regionCode;

	@Enumerated(EnumType.STRING)
	@Column(name = "employment_status", length = 20)
	private EmploymentStatus employmentStatus;

	@Column(name = "income_band", length = 20)
	private String incomeBand;

	@Generated(event = {EventType.INSERT, EventType.UPDATE})
	@Column(name = "updated_at", nullable = false, insertable = false, updatable = false)
	private LocalDateTime updatedAt;

	private UserProfile(User user) {
		this.user = Objects.requireNonNull(user, "user must not be null");
	}

	public static UserProfile create(User user) {
		return new UserProfile(user);
	}

	public void update(
			LocalDate birthDate,
			String regionCode,
			EmploymentStatus employmentStatus,
			String incomeBand
	) {
		this.birthDate = birthDate;
		this.regionCode = regionCode;
		this.employmentStatus = employmentStatus;
		this.incomeBand = incomeBand;
	}
}
