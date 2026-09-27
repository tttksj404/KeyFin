package com.finset.key_fin.transaction.service;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.transaction.repository.SubcategoryQueryRepository;
import com.finset.key_fin.transaction.repository.SubcategoryQueryRow;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.tuple;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class SubcategoryServiceTest {

	private static final long USER_ID = 1L;

	@Mock
	private UserRepository userRepository;

	@Mock
	private SubcategoryQueryRepository subcategoryQueryRepository;

	@InjectMocks
	private SubcategoryService subcategoryService;

	@Test
	void 세분류를_봉투별로_묶어_조회한다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID))
				.willReturn(Optional.of(User.create("qwer@qwer.com", "password", "김예린")));
		given(subcategoryQueryRepository.findAllWithEnvelope()).willReturn(List.of(
				new SubcategoryQueryRow(1, "외식", 101, "음식점"),
				new SubcategoryQueryRow(1, "외식", 102, "카페"),
				new SubcategoryQueryRow(2, "교통비", 201, "대중교통")
		));

		var response = subcategoryService.getSubcategories(USER_ID);

		assertThat(response.items()).hasSize(2);
		assertThat(response.items().getFirst().envelopeName()).isEqualTo("외식");
		assertThat(response.items().getFirst().subcategories())
				.extracting("id", "name")
				.containsExactly(
						tuple(101, "음식점"),
						tuple(102, "카페")
				);
		assertThat(response.items().get(1).envelopeName()).isEqualTo("교통비");
	}

	@Test
	void 활성_사용자가_없으면_세분류를_조회할_수_없다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.empty());

		assertThatThrownBy(() -> subcategoryService.getSubcategories(USER_ID))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode()).isEqualTo(UserErrorCode.USER_NOT_FOUND));
		verifyNoInteractions(subcategoryQueryRepository);
	}
}
