package com.finset.key_fin.user.entity;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.user.exception.UserErrorCode;
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
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.util.Objects;
import java.time.LocalTime;

@Getter
@Entity
@Table(name = "user_settings")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class UserSettings {

	@Id
	@Column(name = "user_id")
	private Long userId;

	@MapsId
	@OneToOne(fetch = FetchType.LAZY, optional = false)
	@JoinColumn(name = "user_id", nullable = false)
	private User user;

	@JdbcTypeCode(SqlTypes.TINYINT)
	@Column(name = "budget_anchor_day", nullable = false)
	private int budgetAnchorDay = 1;

	@Column(name = "transfer_consent", nullable = false)
	private boolean transferConsent = false;

	@Column(name = "transfer_limit_once")
	private Long transferLimitOnce;

	@Column(name = "transfer_limit_daily")
	private Long transferLimitDaily;

	@Enumerated(EnumType.STRING)
	@Column(name = "coach_persona", nullable = false, length = 20)
	private CoachPersona coachPersona = CoachPersona.PLAIN;

	@Column(name = "noti_coaching", nullable = false)
	private boolean notiCoaching = true;

	@Column(name = "noti_budget_alert", nullable = false)
	private boolean notiBudgetAlert = true;

	@Column(name = "noti_transfer", nullable = false)
	private boolean notiTransfer = true;

	@Column(name = "noti_cleanup", nullable = false)
	private boolean notiCleanup = true;

	@Column(name = "quiet_hours_start")
	private LocalTime quietHoursStart;

	@Column(name = "quiet_hours_end")
	private LocalTime quietHoursEnd;

	private UserSettings(User user) {
		this.user = Objects.requireNonNull(user, "user must not be null");
	}

	public static UserSettings create(User user) {
		return new UserSettings(user);
	}

	public void updateBudgetAnchorDay(int budgetAnchorDay) {
		if (budgetAnchorDay < 1 || budgetAnchorDay > 28) {
			throw new BusinessException(UserErrorCode.INVALID_BUDGET_ANCHOR_DAY);
		}
		this.budgetAnchorDay = budgetAnchorDay;
	}

	public void updateTransferSettings(
			boolean transferConsent,
			Long transferLimitOnce,
			Long transferLimitDaily
	) {
		validateTransferLimit(transferLimitOnce);
		validateTransferLimit(transferLimitDaily);
		if (transferLimitOnce != null
				&& transferLimitDaily != null
				&& transferLimitDaily < transferLimitOnce) {
			throw new BusinessException(UserErrorCode.INVALID_TRANSFER_LIMIT);
		}

		this.transferConsent = transferConsent;
		this.transferLimitOnce = transferLimitOnce;
		this.transferLimitDaily = transferLimitDaily;
	}

	public void updateNotificationSettings(
			boolean notiCoaching,
			boolean notiBudgetAlert,
			boolean notiTransfer,
			boolean notiCleanup,
			LocalTime quietHoursStart,
			LocalTime quietHoursEnd
	) {
		validateQuietHours(quietHoursStart, quietHoursEnd);
		this.notiCoaching = notiCoaching;
		this.notiBudgetAlert = notiBudgetAlert;
		this.notiTransfer = notiTransfer;
		this.notiCleanup = notiCleanup;
		this.quietHoursStart = quietHoursStart;
		this.quietHoursEnd = quietHoursEnd;
	}

	public void updateCoachPersona(CoachPersona coachPersona) {
		this.coachPersona = Objects.requireNonNull(coachPersona, "coachPersona must not be null");
	}

	private static void validateQuietHours(LocalTime quietHoursStart, LocalTime quietHoursEnd) {
		boolean hasStart = quietHoursStart != null;
		boolean hasEnd = quietHoursEnd != null;
		if (hasStart != hasEnd || (hasStart && quietHoursStart.equals(quietHoursEnd))) {
			throw new BusinessException(UserErrorCode.INVALID_QUIET_HOURS);
		}
	}

	private static void validateTransferLimit(Long transferLimit) {
		if (transferLimit != null && transferLimit <= 0) {
			throw new BusinessException(UserErrorCode.INVALID_TRANSFER_LIMIT);
		}
	}
}
