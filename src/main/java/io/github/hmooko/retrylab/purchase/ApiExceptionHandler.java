package io.github.hmooko.retrylab.purchase;

import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class ApiExceptionHandler {
    @ExceptionHandler(RetryExhaustedException.class)
    public ResponseEntity<Map<String, Object>> retryExhausted(RetryExhaustedException exception) {
        return ResponseEntity.status(HttpStatus.CONFLICT).body(Map.of(
                "error", "RETRY_EXHAUSTED",
                "strategy", exception.getStrategy().name(),
                "attempts", exception.getAttempts(),
                "retries", exception.getRetries(),
                "firstAttemptConflict", true,
                "elapsedMicros", exception.getElapsedMicros()
        ));
    }

    @ExceptionHandler(IllegalStateException.class)
    public ResponseEntity<Map<String, Object>> illegalState(IllegalStateException exception) {
        return ResponseEntity.status(HttpStatus.CONFLICT).body(Map.of(
                "error", "ILLEGAL_STATE",
                "message", exception.getMessage() == null ? "" : exception.getMessage()
        ));
    }
}
