import http from 'k6/http';
import exec from 'k6/execution';
import { check } from 'k6';
import { Counter, Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';
const STRATEGY = __ENV.STRATEGY || 'OPT_IMMEDIATE';
const HOT_SET = Number(__ENV.HOT_SET || 100);
const RATE = Number(__ENV.RATE || 400);
const TX_WORK_MS = Number(__ENV.TX_WORK_MS || 0);
const MAX_RETRIES = __ENV.MAX_RETRIES === undefined || __ENV.MAX_RETRIES === ''
  ? null
  : Number(__ENV.MAX_RETRIES);
const WARMUP = __ENV.WARMUP || '20s';
const WARMUP_DRAIN = __ENV.WARMUP_DRAIN || '10s';
const DURATION = __ENV.DURATION || '60s';
const REPETITION = Number(__ENV.REPETITION || 1);
const OUTPUT = __ENV.OUTPUT || 'summary.json';
const PRE_ALLOCATED_VUS = Number(__ENV.PRE_ALLOCATED_VUS || 500);
const MAX_VUS = Number(__ENV.MAX_VUS || 1000);
const MEASURE_START = `${parseDurationSeconds(WARMUP) + parseDurationSeconds(WARMUP_DRAIN)}s`;

if (!Number.isFinite(TX_WORK_MS) || TX_WORK_MS < 0) {
  throw new Error(`TX_WORK_MS must be a non-negative number: ${__ENV.TX_WORK_MS}`);
}

if (MAX_RETRIES !== null && (!Number.isInteger(MAX_RETRIES) || MAX_RETRIES < 0)) {
  throw new Error(`MAX_RETRIES must be a non-negative integer: ${__ENV.MAX_RETRIES}`);
}

const successfulPurchases = new Counter('successful_purchases');
const failedPurchases = new Counter('failed_purchases');
const retryAttempts = new Counter('retry_attempts');
const firstAttemptConflicts = new Counter('first_attempt_conflicts');
const purchaseLatency = new Trend('purchase_latency', true);
const purchaseSuccessLatency = new Trend('purchase_success_latency', true);
const purchaseFailureLatency = new Trend('purchase_failure_latency', true);
const successfulRetryDepth0 = new Counter('successful_retry_depth_0');
const successfulRetryDepth1 = new Counter('successful_retry_depth_1');
const successfulRetryDepth2 = new Counter('successful_retry_depth_2');
const successfulRetryDepth3 = new Counter('successful_retry_depth_3');
const successfulRetryDepth4 = new Counter('successful_retry_depth_4');
const successfulRetryDepth5 = new Counter('successful_retry_depth_5');

export const options = {
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(95)', 'p(99)'],
  scenarios: {
    warmup: {
      executor: 'constant-arrival-rate',
      rate: RATE,
      timeUnit: '1s',
      duration: WARMUP,
      gracefulStop: WARMUP_DRAIN,
      preAllocatedVUs: PRE_ALLOCATED_VUS,
      maxVUs: MAX_VUS,
      exec: 'purchase',
    },
    measure: {
      executor: 'constant-arrival-rate',
      rate: RATE,
      timeUnit: '1s',
      startTime: MEASURE_START,
      duration: DURATION,
      preAllocatedVUs: PRE_ALLOCATED_VUS,
      maxVUs: MAX_VUS,
      exec: 'purchase',
    },
  },
  thresholds: {
    'dropped_iterations{scenario:measure}': ['count==0'],
  },
};

export function setup() {
  const productCount = Math.max(100, HOT_SET);
  const reset = http.post(
    `${BASE_URL}/api/admin/reset?productCount=${productCount}&stock=1000000`,
    null,
    { tags: { phase: 'setup' } }
  );

  if (reset.status !== 200) {
    throw new Error(`reset failed: status=${reset.status}, body=${reset.body}`);
  }
}

export function purchase() {
  const productId = Math.floor(Math.random() * HOT_SET) + 1;
  const maxRetriesQuery = MAX_RETRIES === null ? '' : `&maxRetries=${MAX_RETRIES}`;
  const response = http.post(
    `${BASE_URL}/api/purchases/${productId}?strategy=${STRATEGY}&txWorkMs=${TX_WORK_MS}${maxRetriesQuery}`,
    null,
    { tags: { phase: exec.scenario.name } }
  );

  if (exec.scenario.name !== 'measure') {
    return;
  }

  purchaseLatency.add(response.timings.duration);

  let body = null;
  try {
    body = response.json();
  } catch (_) {
    // Count malformed responses as failures below.
  }

  if (body && Number.isFinite(body.retries)) {
    retryAttempts.add(body.retries);
  }

  if (body && body.firstAttemptConflict === true) {
    firstAttemptConflicts.add(1);
  }

  if (response.status === 200) {
    successfulPurchases.add(1);
    purchaseSuccessLatency.add(response.timings.duration);

    if (body && Number.isInteger(body.retries)) {
      switch (body.retries) {
        case 0: successfulRetryDepth0.add(1); break;
        case 1: successfulRetryDepth1.add(1); break;
        case 2: successfulRetryDepth2.add(1); break;
        case 3: successfulRetryDepth3.add(1); break;
        case 4: successfulRetryDepth4.add(1); break;
        case 5: successfulRetryDepth5.add(1); break;
        default: break;
      }
    }
  } else {
    failedPurchases.add(1);
    purchaseFailureLatency.add(response.timings.duration);
  }

  check(response, {
    'purchase completed or retry exhausted': (r) => r.status === 200 || r.status === 409,
  });
}

export function handleSummary(data) {
  const successCount = metricValue(data, 'successful_purchases', 'count', 0);
  const failureCount = metricValue(data, 'failed_purchases', 'count', 0);
  const retryCount = metricValue(data, 'retry_attempts', 'count', 0);
  const firstAttemptConflictCount = metricValue(data, 'first_attempt_conflicts', 'count', 0);
  const p50LatencyMs = metricValue(data, 'purchase_latency', 'med', null);
  const p95LatencyMs = metricValue(data, 'purchase_latency', 'p(95)', null);
  const p99LatencyMs = metricValue(data, 'purchase_latency', 'p(99)', null);

  const successP50LatencyMs = metricValue(data, 'purchase_success_latency', 'med', null);
  const successP95LatencyMs = metricValue(data, 'purchase_success_latency', 'p(95)', null);
  const successP99LatencyMs = metricValue(data, 'purchase_success_latency', 'p(99)', null);

  const failureP50LatencyMs = metricValue(data, 'purchase_failure_latency', 'med', null);
  const failureP95LatencyMs = metricValue(data, 'purchase_failure_latency', 'p(95)', null);
  const failureP99LatencyMs = metricValue(data, 'purchase_failure_latency', 'p(99)', null);

  const successfulRetryDepthCounts = [
    metricValue(data, 'successful_retry_depth_0', 'count', 0),
    metricValue(data, 'successful_retry_depth_1', 'count', 0),
    metricValue(data, 'successful_retry_depth_2', 'count', 0),
    metricValue(data, 'successful_retry_depth_3', 'count', 0),
    metricValue(data, 'successful_retry_depth_4', 'count', 0),
    metricValue(data, 'successful_retry_depth_5', 'count', 0),
  ];
  const durationSeconds = parseDurationSeconds(DURATION);
  const totalDroppedIterations = metricValue(
    data,
    'dropped_iterations',
    'count',
    0
  );
  const droppedIterations = metricValue(
    data,
    'dropped_iterations{scenario:measure}',
    'count',
    0
  );
  const warmupDroppedIterations = Math.max(
    0,
    totalDroppedIterations - droppedIterations
  );

  const completed = successCount + failureCount;
  const result = {
    metadata: {
      strategy: STRATEGY,
      hotSet: HOT_SET,
      rate: RATE,
      txWorkMs: TX_WORK_MS,
      maxRetries: MAX_RETRIES,
      warmup: WARMUP,
      warmupDrain: WARMUP_DRAIN,
      duration: DURATION,
      durationSeconds,
      repetition: REPETITION,
      preAllocatedVUs: PRE_ALLOCATED_VUS,
      maxVUs: MAX_VUS,
    },
    metrics: {
      successCount,
      failureCount,
      retryCount,
      firstAttemptConflictCount,
      firstAttemptConflictRate: completed > 0 ? firstAttemptConflictCount / completed : null,
      throughputPerSecond: durationSeconds > 0 ? successCount / durationSeconds : null,
      p50LatencyMs,
      p95LatencyMs,
      p99LatencyMs,
      successP50LatencyMs,
      successP95LatencyMs,
      successP99LatencyMs,
      failureP50LatencyMs,
      failureP95LatencyMs,
      failureP99LatencyMs,
      retryAmplification: successCount > 0 ? retryCount / successCount : null,
      successfulRetryDepthCounts,
      successfulRetryDepthFractions: successCount > 0
        ? successfulRetryDepthCounts.map((count) => count / successCount)
        : [0, 0, 0, 0, 0, 0],
      failureRate: completed > 0 ? failureCount / completed : null,
      droppedIterations,
      warmupDroppedIterations,
      totalDroppedIterations,
    },
  };

  return {
    [OUTPUT]: JSON.stringify(result, null, 2),
  };
}

function metricValue(data, metricName, valueName, fallback) {
  const metric = data.metrics[metricName];
  if (!metric || !metric.values || metric.values[valueName] === undefined) {
    return fallback;
  }
  return metric.values[valueName];
}

function parseDurationSeconds(value) {
  const match = /^(\d+(?:\.\d+)?)(ms|s|m|h)$/.exec(value);
  if (!match) {
    throw new Error(`unsupported duration format: ${value}`);
  }

  const amount = Number(match[1]);
  const unit = match[2];

  switch (unit) {
    case 'ms':
      return amount / 1000;
    case 's':
      return amount;
    case 'm':
      return amount * 60;
    case 'h':
      return amount * 3600;
    default:
      throw new Error(`unsupported duration unit: ${unit}`);
  }
}
