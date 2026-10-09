package io.github.hmooko.retrylab.purchase;

public record PurchaseResponse(
        PurchaseStrategy strategy,
        int attempts,
        int retries,
        boolean firstAttemptConflict,
        long elapsedMicros
) {}
