package io.github.hmooko.retrylab.purchase;

public enum PurchaseStrategy {
    PESSIMISTIC,
    OPT_IMMEDIATE,
    OPT_FIXED,
    OPT_FIXED_JITTER,
    OPT_EXPONENTIAL,
    OPT_EXPONENTIAL_JITTER
}
