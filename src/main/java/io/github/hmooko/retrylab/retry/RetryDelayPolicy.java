package io.github.hmooko.retrylab.retry;

import io.github.hmooko.retrylab.purchase.PurchaseStrategy;
import java.util.concurrent.ThreadLocalRandom;
import org.springframework.stereotype.Component;

@Component
public class RetryDelayPolicy {
    private final RetrySettings settings;

    public RetryDelayPolicy(RetrySettings settings) {
        this.settings = settings;
    }

    public long delayMillis(PurchaseStrategy strategy, int retryIndex) {
        if (retryIndex < 0) throw new IllegalArgumentException("retryIndex must be >= 0");

        return switch (strategy) {
            case OPT_IMMEDIATE -> 0L;
            case OPT_FIXED -> settings.fixedDelayMs();
            case OPT_FIXED_JITTER -> jitter(settings.fixedDelayMs());
            case OPT_EXPONENTIAL -> exponentialDelay(retryIndex);
            case OPT_EXPONENTIAL_JITTER -> jitter(exponentialDelay(retryIndex));
            case PESSIMISTIC -> throw new IllegalArgumentException("PESSIMISTIC has no retry delay");
        };
    }

    private long exponentialDelay(int retryIndex) {
        long multiplier = 1L << Math.min(retryIndex, 30);
        long uncapped;
        try {
            uncapped = Math.multiplyExact(settings.exponentialBaseMs(), multiplier);
        } catch (ArithmeticException ignored) {
            uncapped = Long.MAX_VALUE;
        }
        return Math.min(uncapped, settings.exponentialCapMs());
    }

    private long jitter(long centerMs) {
        if (centerMs == 0) return 0L;
        double ratio = settings.jitterRatio();
        long lower = Math.max(0L, Math.round(centerMs * (1.0 - ratio)));
        long upper = Math.max(lower, Math.round(centerMs * (1.0 + ratio)));
        if (lower == upper) return lower;
        return ThreadLocalRandom.current().nextLong(lower, upper + 1);
    }
}
