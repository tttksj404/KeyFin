package com.finset.key_fin.global.exception;

import com.finset.key_fin.global.base.BaseResponse;
import lombok.extern.slf4j.Slf4j;
import org.jspecify.annotations.Nullable;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.HttpMediaTypeNotSupportedException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.context.request.WebRequest;
import org.springframework.web.servlet.mvc.method.annotation.ResponseEntityExceptionHandler;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler extends ResponseEntityExceptionHandler {

    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<BaseResponse<Void>> handleBusinessException(BusinessException exception) {
        ErrorCode errorCode = exception.getErrorCode();

        if (errorCode.getHttpStatus().is5xxServerError()) {
            log.error("Business failure: code={}", errorCode.getCode(), exception);
        } else {
            log.warn("Business failure: code={}", errorCode.getCode());
        }

        return ResponseEntity.status(errorCode.getHttpStatus())
                .body(toBody(errorCode));
    }

    @Override
    protected @Nullable ResponseEntity<Object> handleExceptionInternal(
            Exception exception,
            @Nullable Object body,
            HttpHeaders headers,
            HttpStatusCode statusCode,
            WebRequest request
    ) {
        if (statusCode.is5xxServerError()) {
            log.error("MVC failure: status={}", statusCode.value(), exception);
        }

        ErrorCode errorCode = resolveCommonErrorCode(exception, statusCode);

        // Spring MVC가 정한 상태와 헤더, 이미 전송된 응답에 대한 처리를 유지한다.
        return super.handleExceptionInternal(
                exception, toBody(errorCode), headers, statusCode, request
        );
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<BaseResponse<Void>> handleUnexpectedException(Exception exception) {
        log.error("Unhandled exception", exception);

        CommonErrorCode errorCode = CommonErrorCode.INTERNAL_SERVER_ERROR;
        return ResponseEntity.status(errorCode.getHttpStatus())
                .body(toBody(errorCode));
    }

    private ErrorCode resolveCommonErrorCode(Exception exception, HttpStatusCode statusCode) {
        if (exception instanceof HttpMessageNotReadableException) {
            return CommonErrorCode.MESSAGE_NOT_READABLE;
        }
        if (exception instanceof HttpRequestMethodNotSupportedException) {
            return CommonErrorCode.METHOD_NOT_ALLOWED;
        }
        if (exception instanceof HttpMediaTypeNotSupportedException) {
            return CommonErrorCode.UNSUPPORTED_MEDIA_TYPE;
        }
        if (statusCode.value() == 400) {
            return CommonErrorCode.INVALID_INPUT_VALUE;
        }
        if (statusCode.is5xxServerError()) {
            return CommonErrorCode.INTERNAL_SERVER_ERROR;
        }
        return CommonErrorCode.REQUEST_FAILED;
    }

    private BaseResponse<Void> toBody(ErrorCode errorCode) {
        return BaseResponse.fail(errorCode.getCode(), errorCode.getMessage());
    }
}
