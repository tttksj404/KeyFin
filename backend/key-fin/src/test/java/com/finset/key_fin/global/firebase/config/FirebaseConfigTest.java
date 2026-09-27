package com.finset.key_fin.global.firebase.config;

import java.io.IOException;
import com.finset.key_fin.global.firebase.service.FcmSender;
import com.google.auth.oauth2.GoogleCredentials;
import com.google.auth.oauth2.ServiceAccountCredentials;
import com.google.firebase.FirebaseApp;
import com.google.firebase.messaging.FirebaseMessaging;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.mockito.MockedStatic;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyCollection;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.mockStatic;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.when;

class FirebaseConfigTest {

	private final ApplicationContextRunner contextRunner = new ApplicationContextRunner()
			.withUserConfiguration(FirebaseConfig.class);

	@ParameterizedTest
	@ValueSource(strings = {"", "fcm.enabled=false"})
	@DisplayName("활성화 설정이 없거나 false면 인증을 읽지 않고 FCM Bean도 만들지 않는다")
	void disabledDoesNotLoadCredentials(String property) {
		try (MockedStatic<GoogleCredentials> credentials = mockStatic(GoogleCredentials.class)) {
			ApplicationContextRunner runner = property.isEmpty()
					? contextRunner : contextRunner.withPropertyValues(property);
			runner.run(context -> {
				assertThat(context).hasNotFailed()
						.doesNotHaveBean(FirebaseApp.class)
						.doesNotHaveBean(FirebaseMessaging.class)
						.doesNotHaveBean(FcmSender.class);
				credentials.verifyNoInteractions();
			});
		}
	}

	@Test
	@DisplayName("활성화 시 한 번 초기화해 재사용하고 컨텍스트 종료 시 앱을 정리한다")
	void enabledCreatesSingletonsAndDeletesAppOnClose() {
		ServiceAccountCredentials credentials = mock(ServiceAccountCredentials.class);
		when(credentials.getProjectId()).thenReturn("keyfin-fcm-test");
		when(credentials.createScoped(anyCollection())).thenReturn(credentials);
		try (MockedStatic<GoogleCredentials> credentialLoader = mockStatic(GoogleCredentials.class)) {
			credentialLoader.when(GoogleCredentials::getApplicationDefault).thenReturn(credentials);
			// 종료 후 같은 이름으로 다시 시작할 수 있어야 이전 앱이 남지 않은 것이다.
			for (int i = 0; i < 2; i++) {
				contextRunner.withPropertyValues("fcm.enabled=true").run(context -> {
					assertThat(context).hasNotFailed()
							.hasSingleBean(FirebaseApp.class)
							.hasSingleBean(FirebaseMessaging.class)
							.hasSingleBean(FcmSender.class);
					FirebaseApp app = context.getBean(FirebaseApp.class);
					assertThat(app.getName()).isEqualTo("keyfin-fcm");
					assertThat(context.getBean(FirebaseApp.class)).isSameAs(app);
					assertThat(context.getBean(FirebaseMessaging.class)).isSameAs(FirebaseMessaging.getInstance(app));
					assertThat(context.getBean(FcmSender.class)).isSameAs(context.getBean(FcmSender.class));
				});
				assertThat(FirebaseApp.getApps()).noneMatch(app -> app.getName().equals("keyfin-fcm"));
			}
			credentialLoader.verify(GoogleCredentials::getApplicationDefault, times(2));
		}
	}

	@Test
	@DisplayName("활성 상태에서 인증 로딩에 실패하면 컨텍스트 시작도 실패한다")
	void credentialFailurePreventsStartup() {
		IOException failure = new IOException("Test credential loading failure");
		try (MockedStatic<GoogleCredentials> credentialLoader = mockStatic(GoogleCredentials.class)) {
			credentialLoader.when(GoogleCredentials::getApplicationDefault).thenThrow(failure);
			contextRunner.withPropertyValues("fcm.enabled=true").run(context -> {
				assertThat(context).hasFailed();
				assertThat(context.getStartupFailure()).hasRootCause(failure);
			});
			assertThat(FirebaseApp.getApps()).noneMatch(app -> app.getName().equals("keyfin-fcm"));
		}
	}
}
