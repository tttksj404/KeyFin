package com.finset.key_fin.global.firebase.config;

import java.io.IOException;
import com.finset.key_fin.global.firebase.service.FcmSender;
import com.google.auth.oauth2.GoogleCredentials;
import com.google.firebase.FirebaseApp;
import com.google.firebase.FirebaseOptions;
import com.google.firebase.messaging.FirebaseMessaging;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
@ConditionalOnProperty(prefix = "fcm", name = "enabled", havingValue = "true")
public class FirebaseConfig {

	@Bean(destroyMethod = "delete")
	public FirebaseApp firebaseApp() throws IOException {
		FirebaseOptions options = FirebaseOptions.builder()
				.setCredentials(GoogleCredentials.getApplicationDefault())
				.build();
		return FirebaseApp.initializeApp(options, "keyfin-fcm");
	}

	@Bean
	public FirebaseMessaging firebaseMessaging(FirebaseApp firebaseApp) {
		return FirebaseMessaging.getInstance(firebaseApp);
	}

	@Bean
	public FcmSender fcmSender(FirebaseMessaging firebaseMessaging) {
		return new FcmSender(firebaseMessaging);
	}
}
