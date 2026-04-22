# KRA 과거 경마 결과 데이터셋 구축

`race.kra.co.kr`의 경주성적 페이지를 기반으로 과거 결과를 수집하여 데이터셋으로 저장합니다.

## 핵심 요구사항
- 과거 경주 결과 수집
- **모든 베팅식 배당 포함**
  - 단승식
  - 연승식
  - 복승식
  - 쌍승식
  - 복연승식
  - 삼복승식
  - 삼쌍승식

## 제공 스크립트
- `scripts/kra_results_crawler.py`
  - 일별 경주 목록 조회: `ScoretableDailyList.do`
  - 경주별 상세 조회: `ScoretableDetailList.do`
  - 말 단위 결과 CSV + 배당 정규화 CSV 동시 생성

## 출력 파일

### 1) race_results.csv
경주 메타 + 말별 순위/기수/조교사/마주/단승/연승/장구현황 등.

### 2) race_payouts.csv
승식/조합 단위 정규화 배당.
- 예: `bet_type=복승식`, `combination=①⑦`, `odds=8.1`

## 실행 예시

```bash
python scripts/kra_results_crawler.py \
  --start-date 2026-04-19 \
  --end-date 2026-04-19 \
  --meet 서울 \
  --out-results data/race_results_20260419.csv \
  --out-payouts data/race_payouts_20260419.csv
```

## 옵션
- `--meet`: `서울|부산경남|제주` 또는 `1|3|2`
- `--sleep-min`, `--sleep-max`: 요청 간 랜덤 지연(초)

## 참고
- 사이트 인코딩은 EUC-KR 기반이라 스크립트에서 이를 처리합니다.
- 실제 운영 전, 사이트 이용약관/robots 정책을 확인하세요.

## 샘플 데이터셋 (실행 결과)
아래 명령으로 실제 수집을 실행했습니다.

```bash
python scripts/kra_results_crawler.py \
  --start-date 2026-04-19 \
  --end-date 2026-04-19 \
  --meet 1 \
  --out-results data/samples/race_results_2026-04-19_seoul.csv \
  --out-payouts data/samples/race_payouts_2026-04-19_seoul.csv
```

생성 파일:
- `data/samples/race_results_2026-04-19_seoul.csv` (103행)
- `data/samples/race_payouts_2026-04-19_seoul.csv` (110행)

## 2000년~현재 전체 수집 (장기 실행)
전체 기간(2000-01-01 ~ 오늘) + 전체 경마장(서울/제주/부산경남)은 요청 수가 매우 많아 장시간이 필요합니다.
`kra_bulk_collect.py`는 **최근 날짜부터 과거로** 수집하며, 중간 체크포인트를 저장해 중단 후 이어받기를 지원합니다.

```bash
python scripts/kra_bulk_collect.py \
  --start-date 2000-01-01 \
  --end-date 2026-04-22 \
  --meet all \
  --out-results data/full/race_results_full.csv \
  --out-payouts data/full/race_payouts_full.csv \
  --checkpoint data/full/checkpoint.json \
  --resume
```

생성물:
- `data/full/race_results_full.csv`
- `data/full/race_payouts_full.csv`
- `data/full/checkpoint.json`


진행 보고(예: 1시간마다 1회):
```bash
python scripts/kra_bulk_collect.py \
  --start-date 2000-01-01 \
  --end-date 2026-04-22 \
  --meet all \
  --out-results data/full_recent/race_results_full.csv \
  --out-payouts data/full_recent/race_payouts_full.csv \
  --checkpoint data/full_recent/checkpoint.json \
  --resume \
  --report-interval-sec 3600 \
  --report-file data/full_recent/progress.log
```
