package io.github.hmooko.retrylab.purchase;

import io.github.hmooko.retrylab.retry.RetryDelayPolicy;
import io.github.hmooko.retrylab.retry.RetrySettings;
import java.util.concurrent.TimeUnit;
import org.springframework.dao.OptimisticLockingFailureException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class PurchaseService {
    private static final long MAX_TX_WORK_MS = 1_000L;
    private static final int MAX_RETRIES_OVERRIDE = 100;

    private final PurchaseTransactionService transactionService;
    private final RetryDelayPolicy retryDelayPolicy;
    private final RetrySettings retrySettings;

    public PurchaseService(
            PurchaseTransactionService transactionService,
            RetryDelayPolicy retryDelayPolicy,
            RetrySettings retrySettings
    ) {
        this.transactionService = transactionService;
        this.retryDelayPolicy = retryDelayPolicy;
        this.retrySettings = retrySettings;
    }

    public PurchaseResponse purchase(long productId, PurchaseStrategy strategy) {
        return purchase(productId, strategy, 0L, null);
    }

    public PurchaseResponse purchase(long productId, PurchaseStrategy strategy, long txWorkMs) {
        return purchase(productId, strategy, txWorkMs, null);
    }

    public PurchaseResponse purchase(
            long productId,
            PurchaseStrategy strategy,
            long txWorkMs,
            Integer maxRetriesOverride
    ) {
        validateTxWorkMs(txWorkMs);
        int maxRetries = resolveMaxRetries(maxRetriesOverride);
        long startedAt = System.nanoTime();

        if (strategy == PurchaseStrategy.PESSIMISTIC) {
            transactionService.purchasePessimistic(productId, txWorkMs);
            return new PurchaseResponse(strategy, 1, 0, false, elapsedMicros(startedAt));
        }

        int attempts = 0;
        int retries = 0;
        boolean firstAttemptConflict = false;

        while (true) {
            attempts++;
            try {
                transactionService.purchaseOptimistic(productId, txWorkMs);
                return new PurchaseResponse(
                        strategy,
                        attempts,
                        retries,
                        firstAttemptConflict,
                        elapsedMicros(startedAt));
            } catch (OptimisticLockingFailureException conflict) {
                if (attempts == 1) {
                    firstAttemptConflict = true;
                }

                if (retries >= maxRetries) {
                    throw new RetryExhaustedException(
                            strategy, attempts, retries, elapsedMicros(startedAt), conflict);
                }

                long delayMillis = retryDelayPolicy.delayMillis(strategy, retries);
                retries++;
                sleep(delayMillis);
            }
        }
    }

    private void validateTxWorkMs(long txWorkMs) {
        if (txWorkMs < 0 || txWorkMs > MAX_TX_WORK_MS) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "txWorkMs must be between 0 and " + MAX_TX_WORK_MS);
        }
    }

    private int resolveMaxRetries(Integer maxRetriesOverride) {
        if (maxRetriesOverride == null) {
            return retrySettings.maxRetries();
        }
        if (maxRetriesOverride < 0 || maxRetriesOverride > MAX_RETRIES_OVERRIDE) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "maxRetries must be between 0 and " + MAX_RETRIES_OVERRIDE);
        }
        return maxRetriesOverride;
    }

    private void sleep(long delayMillis) {
        if (delayMillis <= 0) return;
        try {
            Thread.sleep(delayMillis);
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("retry sleep interrupted", interrupted);
        }
    }

    private long elapsedMicros(long startedAt) {
        return TimeUnit.NANOSECONDS.toMicros(System.nanoTime() - startedAt);
    }
}
