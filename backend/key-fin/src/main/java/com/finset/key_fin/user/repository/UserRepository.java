package com.finset.key_fin.user.repository;

import com.finset.key_fin.user.entity.User;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface UserRepository extends JpaRepository<User, Long> {

	boolean existsByEmail(String email);

	Optional<User> findByEmail(String email);

	Optional<User> findByEmailAndDeletedAtIsNull(String email);

	Optional<User> findByIdAndDeletedAtIsNull(Long id);

	@Lock(LockModeType.PESSIMISTIC_WRITE)
	@Query("select u from User u where u.id = :userId and u.deletedAt is null")
	Optional<User> findActiveByIdForUpdate(@Param("userId") Long userId);

	boolean existsByFinUserKeyAndIdNot(String finUserKey, Long id);

	List<User> findAllByFinUserKeyIsNotNullAndDeletedAtIsNull();
}
