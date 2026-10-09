package io.github.hmooko.retrylab.retry;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import io.github.hmooko.retrylab.purchase.PurchaseStrategy;
import org.junit.jupiter.api.Test;

class RetryDelayPolicyTest {
    private final RetrySettings settings = new RetrySettings(5, 20, 5, 80, 0.5);
    private final RetryDelayPolicy policy = new RetryDelayPolicy(settings);

    @Test
    void immediateRetryHasNoDelay() {
        assertThat(policy.delayMillis(PurchaseStrategy.OPT_IMMEDIATE, 0)).isZero();
    }

    @Test
    void fixedBackoffAlwaysUsesConfiguredDelay() {
        assertThat(policy.delayMillis(PurchaseStrategy.OPT_FIXED, 0)).isEqualTo(20);
        assertThat(policy.delayMillis(PurchaseStrategy.OPT_FIXED, 4)).isEqualTo(20);
    }

    @Test
    void fixedJitterStaysWithinRange() {
        for (int i = 0; i < 200; i++) {
            assertThat(policy.delayMillis(PurchaseStrategy.OPT_FIXED_JITTER, 0))
                    .isBetween(10L, 30L);
        }
    }

    @Test
    void exponentialBackoffDoublesUntilCap() {
        assertThat(policy.delayMillis(PurchaseStrategy.OPT_EXPONENTIAL, 0)).isEqualTo(5);
        assertThat(policy.delayMillis(PurchaseStrategy.OPT_EXPONENTIAL, 1)).isEqualTo(10);
        assertThat(policy.delayMillis(PurchaseStrategy.OPT_EXPONENTIAL, 2)).isEqualTo(20);
        assertThat(policy.delayMillis(PurchaseStrategy.OPT_EXPONENTIAL, 3)).isEqualTo(40);
        assertThat(policy.delayMillis(PurchaseStrategy.OPT_EXPONENTIAL, 4)).isEqualTo(80);
        assertThat(policy.delayMillis(PurchaseStrategy.OPT_EXPONENTIAL, 5)).isEqualTo(80);
    }

    @Test
    void exponentialJitterStaysWithinRange() {
        for (int i = 0; i < 200; i++) {
            assertThat(policy.delayMillis(PurchaseStrategy.OPT_EXPONENTIAL_JITTER, 3))
                    .isBetween(20L, 60L);
        }
    }

    @Test
    void pessimisticHasNoRetryPolicy() {
        assertThatThrownBy(() -> policy.delayMillis(PurchaseStrategy.PESSIMISTIC, 0))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
