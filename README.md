# KRA 과거 경마 결과 데이터셋 구축 가이드

`race.kra.co.kr`에서 과거 경주 결과를 수집해 머신러닝/분석용 데이터셋을 만드는 실무형 가이드입니다.

## 목표
- 과거 경주 결과를 날짜/경주 단위로 수집
- **모든 베팅식 배당(필수)** 포함
- CSV/Parquet 형태로 적재
- 재수집 시 중복 없이 upsert

## 포함해야 할 핵심 컬럼

### 1) 경주 메타
- `race_date` (YYYY-MM-DD)
- `meet` (서울/부산경남/제주)
- `race_no`
- `race_name`
- `distance_m`
- `track_condition`
- `weather`
- `grade`
- `starter_count`

### 2) 말/기수 결과
- `horse_no`
- `horse_name`
- `finish_rank`
- `running_time`
- `jockey`
- `trainer`
- `owner`
- `body_weight`
- `weight_diff`
- `draw`
- `popularity`

### 3) 배당(반드시 전체)
아래 베팅식은 사이트 표시 기준으로 **행 단위 정규화** 저장을 권장합니다.
- 단승식
- 연승식
- 복승식
- 쌍승식
- 복연승식
- 삼복승식
- 삼쌍승식

> 경주별로 제공되는 베팅식이 다를 수 있으므로, 비어 있는 베팅식은 `NULL` 처리하고 스키마는 고정하세요.

## 권장 스키마

### `race_results` (경주 메타 + 말별 순위)
- PK: `(race_date, meet, race_no, horse_no)`

### `race_payouts` (배당 정규화)
- PK: `(race_date, meet, race_no, bet_type, combination)`
- 예시
  - `bet_type=복승식`, `combination=3-7`, `odds=12.4`
  - `bet_type=삼쌍승식`, `combination=3-7-11`, `odds=84.1`

## 수집 전략 (안정성 우선)

1. **목록 페이지**에서 날짜별 경주 링크 확보
2. **상세 페이지**에서
   - 경주 메타/출주 결과 테이블 파싱
   - 배당 테이블 파싱
3. 행 단위 정규화 후 저장
4. 체크포인트(마지막 성공 날짜/경주) 기록
5. 실패 요청 자동 재시도 + 지수 백오프

## 운영 팁
- `User-Agent` 명시
- 요청 간 딜레이(예: 0.7~1.5초 랜덤)
- HTTP 429/5xx 재시도
- HTML 구조 변경 감지(필수 컬럼 누락 시 에러)
- 수집 로그 분리(`crawl.log`)

## 실행 예시

```bash
python scripts/kra_results_crawler.py \
  --start-date 2020-01-01 \
  --end-date 2020-12-31 \
  --meet 서울 \
  --out data/kra_2020.csv
```

## 주의
- 사이트 이용약관/robots 정책을 먼저 확인하세요.
- 상업적 이용/재배포 전 법적 검토를 권장합니다.

## 다음 단계
- 원하시면 제가 `race.kra.co.kr` 실제 HTML 구조 기준으로 CSS selector/XPath를 맞춰서,
  바로 수집 가능한 버전으로 고도화해드릴 수 있습니다.
