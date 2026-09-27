package com.finset.key_fin.link.service;

import com.finset.key_fin.global.exception.BusinessException;
import com.finset.key_fin.global.exception.ErrorCode;
import com.finset.key_fin.link.dto.request.LinkAssetsRequest;
import com.finset.key_fin.link.dto.response.LinkAssetsResponse;
import com.finset.key_fin.link.exception.LinkErrorCode;
import com.finset.key_fin.user.entity.User;
import com.finset.key_fin.user.exception.UserErrorCode;
import com.finset.key_fin.user.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;
import java.util.Optional;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class AssetLinkServiceTest {

	private static final long USER_ID = 1L;

	@Mock
	private UserRepository userRepository;

	@Mock
	private AssetLinkWriter assetLinkWriter;

	@InjectMocks
	private AssetLinkService assetLinkService;

	private User user;

	@BeforeEach
	void setUp() {
		user = User.create("qwer@qwer.com", "encoded-password", "김예린");
		ReflectionTestUtils.setField(user, "id", USER_ID);
	}

	@Test
	void 중복을_제거한_ID_목록으로_연결을_위임한다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(assetLinkWriter.link(USER_ID, Set.of(3L, 4L), Set.of(7L))).willReturn(new LinkAssetsResponse(2, 1));

		LinkAssetsResponse response = assetLinkService.link(
				USER_ID, new LinkAssetsRequest(List.of(3L, 4L, 3L), List.of(7L)));

		assertThat(response.accounts()).isEqualTo(2);
		assertThat(response.cards()).isEqualTo(1);
		verify(assetLinkWriter).link(USER_ID, Set.of(3L, 4L), Set.of(7L));
	}

	@Test
	void 카드만_선택하면_계좌_목록은_비어_있는_채로_위임한다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));
		given(assetLinkWriter.link(USER_ID, Set.of(), Set.of(7L))).willReturn(new LinkAssetsResponse(0, 1));

		LinkAssetsResponse response = assetLinkService.link(USER_ID, new LinkAssetsRequest(null, List.of(7L)));

		assertThat(response.cards()).isEqualTo(1);
	}

	@Test
	void 선택_항목이_없으면_거절한다() {
		assertBusinessError(
				LinkErrorCode.EMPTY_LINK_REQUEST,
				() -> assetLinkService.link(USER_ID, new LinkAssetsRequest(List.of(), null))
		);
		verifyNoInteractions(userRepository, assetLinkWriter);
	}

	@Test
	void 탈퇴했거나_없는_사용자는_연결할_수_없다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.empty());

		assertBusinessError(
				UserErrorCode.USER_NOT_FOUND,
				() -> assetLinkService.link(USER_ID, new LinkAssetsRequest(List.of(3L), List.of()))
		);
		verifyNoInteractions(assetLinkWriter);
	}

	@Test
	void 계좌_연결_해제는_활성_사용자_확인_후_위임한다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.of(user));

		assetLinkService.unlinkAccount(USER_ID, 10L);

		verify(assetLinkWriter).unlinkAccount(USER_ID, 10L);
	}

	@Test
	void 탈퇴한_사용자는_카드_연결을_해제할_수_없다() {
		given(userRepository.findByIdAndDeletedAtIsNull(USER_ID)).willReturn(Optional.empty());

		assertBusinessError(UserErrorCode.USER_NOT_FOUND, () -> assetLinkService.unlinkCard(USER_ID, 20L));
		verifyNoInteractions(assetLinkWriter);
	}

	private void assertBusinessError(ErrorCode expectedErrorCode, Runnable action) {
		assertThatThrownBy(action::run)
				.isInstanceOf(BusinessException.class)
				.extracting(exception -> ((BusinessException) exception).getErrorCode())
				.isEqualTo(expectedErrorCode);
	}
}
