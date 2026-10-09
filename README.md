# 낙관적 락 재시도 전략 — 제출 논문 재현용 코드 (n=30)

> **제출 논문 보존본:** 경합 수준에 따른 낙관적 락 재시도 전략의 성공률–지연시간 trade-off 분석. 이 브랜치는 제출 시점의 실험에 필요한 코드와 원본 데이터만 보존합니다. 새로운 정책 개발은 `main`에서 진행하고, `paper/submitted-n30-reproduction`은 제출 논문 검증용으로 유지합니다.

## 1. 연구 개요 (논문의 주요 내용)

Spring Boot/JPA와 MySQL의 단일 상품 재고 감소 API에서 낙관적 락 충돌이 발생했을 때 재시도 시점이 최종 성공률, 성공 요청의 tail latency, 재시도 부하에 어떤 영향을 주는지 비교합니다. `HOT_SET=1`로 하나의 row에 요청이 집중되도록 했으며, 트랜잭션 내부에 `txWork=10ms`의 synthetic delay를 삽입했습니다.

비교한 전략은 **Immediate, Fixed, Fixed+Jitter, Exponential, Exponential+Jitter** 총 5개입니다. 첫 시도 OCC 충돌률은 **재시도를 끈 상태(`maxRetries=0`)에서 별도 측정**하여 baseline conflict rate로 사용합니다. 따라서 이 값은 특정 하드웨어·workload에서 관측된 경합 지표이며, 실제 재시도 실행 중의 conflict rate와 동일한 개념이 아닙니다.

5개 RPS(64, 68, 72, 76, 88) × 5개 정책 × 30회 반복으로 본 실험 **750 runs**를 수행했습니다. 처음 10회(250 runs)와 추가 20회(500 runs)는 별도 cohort로 저장했고, 결과는 **각 조건의 run별 지표 중앙값**을 사용했습니다. RPS88 retry-depth만 30개 run의 요청 건수를 합산(pooled)합니다.

### 결과와 결론

- 낮은 baseline conflict **0.57~3.23%**에서는 최종 성공률이 거의 비슷한 반면, Immediate의 성공 요청 p99 latency가 가장 낮습니다.
- 중간 수준 **11.38%**에서는 일부 backoff 전략의 성공률 이점이 나타나기 시작합니다.
- 높은 conflict **41.01%**에서 Immediate의 성공률은 **73.345%**, Exp+Jitter는 **78.468%**(약 **+5.123%p**)였습니다. Retry amplification은 **3.400 → 2.898**로 감소하지만, success-only p99는 **97.60 → 277.95ms**로 증가했습니다.
- Fixed는 가장 높은 경합에서 Immediate보다도 성공률이 낮아, **backoff가 무조건 유리한 것은 아님**을 보여줍니다.
- Retry-depth에서는 일부 backoff 전략이 1~2회 retry 후 성공하는 요청의 비중을 높이고 최종 실패 비중을 낮추는 패턴을 보였습니다. 이 분포 자체만으로 동기화 등의 구체적인 인과 메커니즘까지 입증한 것은 아닙니다.
- 결론: **낮은 경합에서는 Immediate가 유리하지만, 경합이 높아질수록 적절한 backoff의 성공률·재시도 효율상 이점이 증가하며 추가 latency를 지불**합니다. 최적 정책은 서비스가 중요하게 여기는 성능 목표에 따라 달라집니다.

### n=30 수치 요약 (조건별 run 중앙값)

아래 표의 열은 baseline first-attempt OCC conflict(%), RPS, 재시도 정책, 최종 성공률(%), success-only p99(ms), retry amplification입니다. q1/q3 등 자세한 값은 [`paper-data/paper_metrics.csv`](paper-data/paper_metrics.csv)에 있습니다.

| Conflict | RPS | 전략 | 성공률 (%) | 성공 p99 (ms) | Retry amplification |
|---:|---:|---|---:|---:|---:|
| 0.57% | 64 | Immediate | 99.323 | 30.37 | 0.046 |
| 0.57% | 64 | Fixed | 99.297 | 127.81 | 0.093 |
| 0.57% | 64 | Fixed+Jitter | 99.349 | 115.82 | 0.098 |
| 0.57% | 64 | Exponential | 99.297 | 66.80 | 0.067 |
| 0.57% | 64 | Exp+Jitter | 99.297 | 83.34 | 0.080 |
| 3.23% | 68 | Immediate | 97.170 | 62.62 | 0.193 |
| 3.23% | 68 | Fixed | 97.072 | 167.64 | 0.287 |
| 3.23% | 68 | Fixed+Jitter | 97.525 | 166.11 | 0.248 |
| 3.23% | 68 | Exponential | 97.403 | 167.23 | 0.244 |
| 3.23% | 68 | Exp+Jitter | 97.390 | 164.55 | 0.265 |
| 11.38% | 72 | Immediate | 91.761 | 100.24 | 0.703 |
| 11.38% | 72 | Fixed | 92.339 | 200.59 | 0.715 |
| 11.38% | 72 | Fixed+Jitter | 93.543 | 199.32 | 0.669 |
| 11.38% | 72 | Exponential | 93.485 | 255.88 | 0.719 |
| 11.38% | 72 | Exp+Jitter | 93.277 | 252.72 | 0.716 |
| 24.99% | 76 | Immediate | 85.331 | 98.81 | 1.579 |
| 24.99% | 76 | Fixed | 87.064 | 202.15 | 1.330 |
| 24.99% | 76 | Fixed+Jitter | 88.477 | 204.98 | 1.336 |
| 24.99% | 76 | Exponential | 88.895 | 256.07 | 1.303 |
| 24.99% | 76 | Exp+Jitter | 88.950 | 267.77 | 1.308 |
| 41.01% | 88 | Immediate | 73.345 | 97.60 | 3.400 |
| 41.01% | 88 | Fixed | 71.849 | 197.94 | 3.096 |
| 41.01% | 88 | Fixed+Jitter | 77.644 | 208.61 | 3.051 |
| 41.01% | 88 | Exponential | 78.300 | 251.25 | 3.063 |
| 41.01% | 88 | Exp+Jitter | 78.468 | 277.95 | 2.898 |

RPS88의 pooled retry-depth (0~5 retry 성공과 최종 실패)는 [`paper-data/paper_rps88_retry_depth.csv`](paper-data/paper_rps88_retry_depth.csv)에서 확인할 수 있습니다. 이 수치는 **전체 논리 요청 대비 비율**이며, run별 중앙값이 아닙니다.

## 2. 실험 환경 및 정책 설정

| 구성 요소 | 환경 / 설정 |
|---|---|
| Load server | k6 2.3.0, 2 vCPU / 2 GB container |
| Application server | Spring Boot/JPA, Java 21, 2 vCPU / 4 GB container, 2 GB JVM heap |
| Database server | MySQL 8.4.11, `READ COMMITTED`, 3 vCPU / 8 GB container, 4 GB InnoDB buffer pool |
| Workload | `HOT_SET=1`, `TX_WORK_MS=10` (transaction 내부 synthetic delay) |
| Retry 횟수 | 최대 5회 (첫 시도 포함 총 최대 6 attempts) |
| Fixed | 항상 20ms 대기 |
| Fixed+Jitter | 20ms의 ±50% 균등 무작위 jitter (10~30ms) |
| Exponential | 5/10/20/40/80ms 순차 증가 |
| Exponential+Jitter | 각 exponential 지연에 ±50% jitter 적용 |
| 측정 | warmup 20초, drain 10초, measurement 60초, 반복마다 조건 순서 shuffle |
| k6 concurrency | `PRE_ALLOCATED_VUS=1500`, `MAX_VUS=3000` |

서비스 환경 설정은 `pom.xml`, `src/main/resources/application.yml`, `deploy/{app,db,load}/compose.yml`에서 확인할 수 있습니다. 실제 서버마다 컨테이너 자원 공유 및 시스템 부하가 달라질 수 있으므로 성능값이 비트 단위로 동일하게 나오는 것은 보장되지 않습니다.

## 3. 저장소 구조

```text
src/main/                         # 재고 감소 API / 낙관적 락 / 5개 retry policy
src/test/                         # 재시도 정책 및 동시성 테스트
k6/benchmark.js                   # 논문의 측정 지표 수집
deploy/{app,db,load}/             # 3서버 Docker 환경
scripts/run-conflict-calibration.sh
scripts/run-conflict-strategy-matrix.sh
scripts/run-k6-docker.sh
scripts/aggregate_paper.py        # 검증 및 n=30 통계 집계
scripts/plot_paper.py             # 그림 2~5 재생성
data/calibration/                 # baseline calibration 원본 JSON 42개 + TSV
data/raw/first10/                 # 본 실험 처음 250개 JSON
data/raw/additional20/            # 본 실험 추가 500개 JSON
data/SHA256SUMS                   # 792 JSON 각각의 SHA-256
paper-data/                       # 제출 논문의 compact 결과 CSV
requirements-analysis.txt        # 그래프 생성 의존성
```

과거 txWork/HOT_SET 탐색 실험, 비관적 락 비교, 별도 모니터링 서비스, 사용하지 않는 실험 스크립트는 제거했습니다. **원본 JSON 파일은 추가 가공하지 않고 원래 측정 결과 그대로 보존**합니다. 파일별 실행 로그는 포함하지 않았습니다.

## 4. 원본 데이터로 논문 결과 즉시 재현 (실험 재실행 불필요)

Python 3.12 이상을 권장합니다. 저장소 루트에서 다음 순서로 실행하세요.

```bash
# 원본 JSON 792개가 보존된 파일인지 확인
sha256sum -c data/SHA256SUMS

# 두 본 실험 cohort 합산: 750 runs = 25조건 × 30회
python3 scripts/aggregate_paper.py \
  --input data/raw/first10 data/raw/additional20 \
  --out results/paper-n30 --expected-n 30

# 생성된 CSV가 제출 논문 숫자와 동일한지 확인
diff -u paper-data/paper_metrics.csv results/paper-n30/paper_metrics.csv
diff -u paper-data/paper_rps88_retry_depth.csv results/paper-n30/paper_rps88_retry_depth.csv

# 그림 2(성공률) ~ 그림 5(retry-depth) 재생성
python3 -m pip install -r requirements-analysis.txt
python3 scripts/plot_paper.py \
  --input results/paper-n30 --out results/paper-n30/figures
```

**산출물**: `paper_metrics.csv`(조건별 지표 중앙값과 IQR), `paper_runs.csv`(각 run의 metrics), `paper_rps88_retry_depth.csv`(RPS88 pooled retry-depth). 그래프 PNG 4개는 `results/paper-n30/figures/`에 저장됩니다. 결과 디렉터리는 `.gitignore`로 제외되어 있습니다.

### Baseline calibration 원본 검사

`data/calibration/`에는 14개 RPS × 3회의 calibration JSON 42개, `summary.tsv`, `runs.tsv`가 보존되어 있습니다. 논문에 사용한 다섯 개 지점의 관측값은 다음과 같습니다.

| RPS | Baseline first-attempt OCC conflict (3회 중앙값) |
|---:|---:|
| 64 | 0.57% |
| 68 | 3.23% |
| 72 | 11.38% |
| 76 | 24.99% |
| 88 | 41.01% |

더 자세한 수치는 [`data/calibration/summary.tsv`](data/calibration/summary.tsv)에 있습니다.

## 5. 새로운 환경에서 부하 실험까지 다시 실행

**주의:** 이 프로젝트는 실험용 API이며 재고 전체를 재설정하는 admin endpoint가 있습니다. 반드시 접근이 제한된 사설 네트워크에서 실행하세요.

세 대의 Linux 서버(Load/App/DB)에 이 저장소를 같은 리비전으로 체크아웃합니다. 앱과 DB 서버에 `.env.example`을 `.env`로 복사하여 **사설 DB 주소**와 새 실험용 비밀번호를 입력합니다. `.env`는 Git에 올리지 마세요.

```bash
# DB server
docker compose -f deploy/db/compose.yml up -d

# App server
docker compose -f deploy/app/compose.yml up -d --build
curl -fsS http://127.0.0.1:8080/actuator/health
```

기존 논문의 x축을 재확인하려면 Load 서버에서 `maxRetries=0`인 calibration을 먼저 수행합니다. 아래는 논문에 사용한 RPS 5개만 재확인하는 명령입니다. 14개 전 구간을 재확인하려면 [`data/calibration/summary.tsv`](data/calibration/summary.tsv)의 RPS를 사용하세요.

```bash
BASE_URL=http://APP_PRIVATE_IP:8080 \
RATES="64 68 72 76 88" HOT_SET=1 TX_WORK_MS=10 \
REPETITIONS=3 bash scripts/run-conflict-calibration.sh
```

그다음 원래의 **10회 + 추가 20회**를 분리해 수행합니다. 기존 포함 데이터는 덮어쓰지 않도록 반드시 `results/` 아래 새 경로에 저장하세요.

```bash
# 최초 cohort: 조건별 10회 = 250 runs
BASE_URL=http://APP_PRIVATE_IP:8080 RATES="64 68 72 76 88" \
HOT_SET=1 TX_WORK_MS=10 REPETITIONS=10 \
WARMUP=20s WARMUP_DRAIN=10s DURATION=60s \
PRE_ALLOCATED_VUS=1500 MAX_VUS=3000 \
OUTDIR=results/reproduced-first10 \
bash scripts/run-conflict-strategy-matrix.sh

# 추가 cohort: 조건별 20회 = 500 runs
BASE_URL=http://APP_PRIVATE_IP:8080 RATES="64 68 72 76 88" \
HOT_SET=1 TX_WORK_MS=10 REPETITIONS=20 \
WARMUP=20s WARMUP_DRAIN=10s DURATION=60s \
PRE_ALLOCATED_VUS=1500 MAX_VUS=3000 \
OUTDIR=results/reproduced-additional20 \
bash scripts/run-conflict-strategy-matrix.sh

# 새 실험 데이터로 n=30 재집계
python3 scripts/aggregate_paper.py \
  --input results/reproduced-first10 results/reproduced-additional20 \
  --out results/reproduced-paper-n30 --expected-n 30
```

스크립트는 각 실험 조건을 반복마다 무작위 순서로 실행하고, JSON 누락·중복·설정 불일치·측정 dropped iteration·retry-depth 합계 오류를 검사할 수 있습니다. **실험 환경이 다르다면 재측정 수치와 baseline conflict의 대응관계는 달라질 수 있습니다.**

## 6. 지표 정의·한계·향후 연구

- **Final success rate:** 성공한 논리 요청 수 / 완료된 전체 논리 요청 수.
- **Success-only p99:** 성공한 요청의 응답시간 99백분위수. 실패 요청을 포함하는 전체 p99와 구별합니다.
- **Retry amplification:** `total retry attempts / successful logical requests`.
- **RPS88 pooled retry depth:** 전체 요청 중 0~5회 재시도 후 성공하거나 최종 실패한 요청의 비중. 각 run의 백분율 중앙값이 아닙니다.

본 연구는 단일 hot row(`HOT_SET=1`), 특정 컴퓨팅 환경, txWork=10ms synthetic delay라는 제한이 있습니다. 각 retry 정책의 실시간 적응형 최적화를 검증한 실험도 아닙니다. 후속 연구에서는 conflict 비율을 더 촘촘하게 바꿔 **어느 경합 수준부터 어떤 backoff가 Immediate보다 유리해지는지**를 분석하고, 다른 HOT_SET과 transaction-work 조건으로 일반화 가능성을 검증할 계획입니다.

## 7. 보존 정책

- **`paper/submitted-n30-reproduction`**: 제출 논문 원본 코드·JSON·README를 고정하는 재현용 브랜치. 앞으로 개발 변경을 병합하지 않습니다.
- **`main`**: 이 브랜치와 동일한 상태에서 출발해 향후 실험·분석을 추가하는 개발 브랜치.
- 실험용 DB 자격 증명은 `.env.example`에 더미 값만 남겼습니다. 기존 Git 히스토리에 과거 실험 설정이 남아 있을 수 있으므로 예전에 사용한 암호는 실제 서비스에 재사용하지 마세요.
