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

## 실제 요청 URL 정리

현재 스크립트(`scripts/kra_bulk_collect.py`, `scripts/kra_results_crawler.py`)가 실제로 호출하는 URL은 아래와 같습니다.

### 1) 일자별 경주 목록
- 용도: 해당 날짜/경마장(서울/부산경남/제주)의 경주 키(`meet`, `realRcDate`, `realRcNo`) 수집
- 템플릿:

```text
https://race.kra.co.kr/raceScore/ScoretableDetailList.do?meet={meet_code}&realRcDate={yyyymmdd}
```

- 예시(서울, 2026-04-19):

```text
https://race.kra.co.kr/raceScore/ScoretableDetailList.do?meet=1&realRcDate=20260419
```

### 2) 경주 상세(성적 + 기본 배당)
- 용도: 경주 메타/말별 성적 + 상세 페이지 내 배당률 표 파싱
- 템플릿:

```text
https://race.kra.co.kr/raceScore/ScoretableDetail.do?meet={meet_code}&realRcDate={yyyymmdd}&realRcNo={race_no}
```

- 예시(서울, 2026-04-19, 1경주):

```text
https://race.kra.co.kr/raceScore/ScoretableDetail.do?meet=1&realRcDate=20260419&realRcNo=1
```

### 3) 배당률 상세(추가 배당 페이지)
- 용도: 상세 페이지에서 `배당` 링크(또는 `odds` 문자열 포함 href)를 발견했을 때 추가 호출
- 특징: URL 패턴은 고정 1개가 아니라, 상세 페이지에 포함된 링크를 **동적으로 추출**
- 대표 예시(테스트 fixture 기준):

```text
https://race.kra.co.kr/raceScore/oddsExample.do?meet=1&realRcDate=20260419&realRcNo=1
```

> 즉, “각 배당률(단승/연승/복승/쌍승/복연승/삼복/삼쌍) URL”이 베팅식별로 분리된 것이 아니라,
> 기본적으로 `ScoretableDetail.do` + (필요 시) 추가 배당 링크 URL에서 함께 파싱합니다.

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
