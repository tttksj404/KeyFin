package com.finset.key_fin.global.firebase.service;

import com.finset.key_fin.global.firebase.config.FirebaseConfig;
import com.finset.key_fin.notification.repository.PushDeviceRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.*;
import org.springframework.core.env.Environment;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.test.annotation.DirtiesContext;
import java.util.Map;
import static org.assertj.core.api.Assertions.assertThat;

/** Explicit opt-in. No application scan, migrations, Redis, or schedulers. */
@SpringBootTest(classes=FcmDatabaseManualTest.Config.class, webEnvironment=SpringBootTest.WebEnvironment.NONE,
        properties="fcm.enabled=true")
@EnabledIfEnvironmentVariable(named="FCM_MANUAL_TEST", matches="true")
@EnabledIfEnvironmentVariable(named="FCM_TEST_USER_ID", matches="[1-9][0-9]*")
@DirtiesContext(classMode=DirtiesContext.ClassMode.AFTER_CLASS)
class FcmDatabaseManualTest {
    @Autowired FcmSender sender;
    @Autowired PushDeviceRepository devices;

    @Test void sendToRegisteredDevices() throws Exception {
        long userId = Long.parseLong(System.getenv("FCM_TEST_USER_ID"));
        var active = devices.findActiveByUserId(userId);
        assertThat(active).as("로그인 후 활성 기기가 DB에 등록되어 있어야 합니다.").isNotEmpty();
        for (var device : active) {
            String messageId = sender.send(device.fcmToken(), "KeyFin DB 기기 테스트",
                    "등록된 기기 정보로 보낸 알림입니다.", Map.of("type", "TEST"));
            System.out.println("FCM accepted: deviceId=" + device.id() + ", messageId=" + messageId);
        }
    }

    @Configuration(proxyBeanMethods=false)
    @Import({FirebaseConfig.class, PushDeviceRepository.class})
    static class Config {
        @Bean JdbcClient jdbcClient(Environment environment) {
            return JdbcClient.create(new DriverManagerDataSource(
                    environment.getRequiredProperty("spring.datasource.url"),
                    environment.getRequiredProperty("spring.datasource.username"),
                    environment.getRequiredProperty("spring.datasource.password")));
        }
    }
}
