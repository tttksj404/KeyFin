package com.finset.key_fin;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

import java.time.ZoneId;
import java.util.TimeZone;

@SpringBootApplication
public class KeyFinApplication {

	public static void main(String[] args) {
		// TODO(hj): 서비스 로직에서 KST 
		TimeZone.setDefault(TimeZone.getTimeZone(ZoneId.of("Asia/Seoul")));
		SpringApplication.run(KeyFinApplication.class, args);
	}

}
