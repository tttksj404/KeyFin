package com.finset.key_fin.coaching.repository;

import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

import com.finset.key_fin.coaching.entity.CoachingSession;

public interface CoachingSessionRepository extends JpaRepository<CoachingSession, Long> {

	Optional<CoachingSession> findByUserId(Long userId);
}
