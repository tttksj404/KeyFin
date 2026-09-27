package com.finset.key_fin.notification;

import com.finset.key_fin.auth.config.*;
import com.finset.key_fin.auth.jwt.JwtTokenProvider;
import com.finset.key_fin.auth.security.*;
import com.finset.key_fin.global.firebase.config.FirebaseConfig;
import com.finset.key_fin.notification.controller.PushDeviceController;
import com.finset.key_fin.notification.dto.request.PushDeviceRequest;
import com.finset.key_fin.notification.service.PushDeviceService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import java.util.UUID;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(controllers=PushDeviceController.class, properties={"fcm.enabled=false", "jwt.secret=push-test-secret-at-least-thirty-two-characters"})
@Import({SecurityConfig.class, AuthConfig.class, JwtTokenProvider.class, JwtAuthenticationFilter.class,
        JwtAuthenticationEntryPoint.class, JwtAccessDeniedHandler.class, SecurityErrorResponseWriter.class, FirebaseConfig.class})
class PushDeviceControllerTest {
    @Autowired MockMvc mvc;
    @Autowired JwtTokenProvider jwt;
    @MockitoBean PushDeviceService service;
    final String id = UUID.randomUUID().toString();
    String path() { return "/api/v1/me/push-devices/" + id; }
    String bearer() { return "Bearer " + jwt.generateAccessToken(42); }

    @Test void authenticatedRegistrationWorksWithFirebaseDisabledAndReturnsNoToken() throws Exception {
        mvc.perform(put(path()).header("Authorization", bearer()).contentType("application/json")
                .content("{\"token\":\"test-token\",\"platform\":\"ANDROID\"}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data").doesNotExist());
        verify(service).register(42, UUID.fromString(id), new PushDeviceRequest("test-token","ANDROID"));
    }
    @Test void deleteUsesAuthenticatedOwner() throws Exception {
        mvc.perform(delete(path()).header("Authorization", bearer())).andExpect(status().isOk());
        verify(service).disconnect(42, UUID.fromString(id));
    }
    @Test void bothEndpointsRequireAuthentication() throws Exception {
        mvc.perform(put(path()).contentType("application/json").content("{\"token\":\"test\",\"platform\":\"ANDROID\"}"))
                .andExpect(status().isUnauthorized());
        mvc.perform(delete(path())).andExpect(status().isUnauthorized());
        verifyNoInteractions(service);
    }
    @ParameterizedTest
    @ValueSource(strings={"", " ", "with space", "한글", "line\nbreak", "\u007f", "tab\tvalue"})
    void invalidTokensAreRejected(String token) throws Exception {
        String body = new tools.jackson.databind.ObjectMapper().writeValueAsString(new PushDeviceRequest(token, "ANDROID"));
        mvc.perform(put(path()).header("Authorization", bearer()).contentType("application/json").content(body))
                .andExpect(status().isBadRequest());
        verifyNoInteractions(service);
    }
    @Test void overlongTokenMissingTokenUnsupportedPlatformAndMalformedUuidAreRejected() throws Exception {
        for (String body : new String[]{
                "{\"token\":\"" + "a".repeat(2049) + "\",\"platform\":\"ANDROID\"}",
                "{\"platform\":\"ANDROID\"}", "{\"token\":\"token\",\"platform\":\"IOS\"}"}) {
            mvc.perform(put(path()).header("Authorization", bearer()).contentType("application/json").content(body))
                    .andExpect(status().isBadRequest());
        }
        for (String invalid : new String[]{"not-a-uuid", "1-1-1-1-1"}) {
            mvc.perform(put("/api/v1/me/push-devices/" + invalid).header("Authorization", bearer())
                    .contentType("application/json").content("{\"token\":\"token\",\"platform\":\"ANDROID\"}"))
                    .andExpect(status().isBadRequest());
        }
        verifyNoInteractions(service);
    }
}
