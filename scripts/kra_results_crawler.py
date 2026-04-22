#!/usr/bin/env python3
"""KRA 과거 경주 결과/배당 수집기 (템플릿)

주의:
- 실제 운영 전에는 대상 페이지의 HTML 구조에 맞춰 selector를 조정해야 한다.
- 이 스크립트는 데이터 모델과 파이프라인 골격 제공이 목적이다.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import random
import time
from pathlib import Path
from typing import Iterable
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

BET_TYPES = ["단승식", "연승식", "복승식", "쌍승식", "복연승식", "삼복승식", "삼쌍승식"]


@dataclasses.dataclass
class RacePayout:
    race_date: str
    meet: str
    race_no: int
    bet_type: str
    combination: str
    odds: str


@dataclasses.dataclass
class HorseResult:
    race_date: str
    meet: str
    race_no: int
    horse_no: int
    horse_name: str
    finish_rank: str
    running_time: str
    jockey: str
    trainer: str
    owner: str


def daterange(start: dt.date, end: dt.date) -> Iterable[dt.date]:
    cursor = start
    while cursor <= end:
        yield cursor
        cursor += dt.timedelta(days=1)


def fetch_html(url: str, timeout: int = 20) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as res:
        return res.read().decode("utf-8", errors="replace")


def build_daily_url(race_date: dt.date, meet: str) -> str:
    date_s = race_date.strftime("%Y%m%d")
    # TODO: 실제 race.kra.co.kr 결과 조회 URL 규격으로 교체
    return f"https://race.kra.co.kr/results?date={date_s}&meet={quote_plus(meet)}"


def parse_daily_page(_html: str, _race_date: dt.date, _meet: str) -> tuple[list[HorseResult], list[RacePayout]]:
    """TODO: 실제 HTML 구조에 맞게 구현.

    구현 시 가이드:
    - 경주별 결과 표에서 horse result 추출
    - 배당 표에서 BET_TYPES 모두 추출
    - 배당은 (bet_type, combination, odds) 행으로 정규화
    """
    return [], []


def write_csv(path: str, rows: list[dict], fieldnames: list[str]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--meet", required=True, help="서울|부산경남|제주")
    parser.add_argument("--out-results", default="data/race_results.csv")
    parser.add_argument("--out-payouts", default="data/race_payouts.csv")
    args = parser.parse_args()

    start = dt.datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end = dt.datetime.strptime(args.end_date, "%Y-%m-%d").date()

    all_results: list[HorseResult] = []
    all_payouts: list[RacePayout] = []

    for d in daterange(start, end):
        url = build_daily_url(d, args.meet)
        print(f"[INFO] Fetching {url}")
        try:
            html = fetch_html(url)
            results, payouts = parse_daily_page(html, d, args.meet)
            all_results.extend(results)
            all_payouts.extend(payouts)
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] {d} 수집 실패: {e}")

        time.sleep(random.uniform(0.7, 1.5))

    write_csv(
        args.out_results,
        [dataclasses.asdict(r) for r in all_results],
        [f.name for f in dataclasses.fields(HorseResult)],
    )
    write_csv(
        args.out_payouts,
        [dataclasses.asdict(p) for p in all_payouts],
        [f.name for f in dataclasses.fields(RacePayout)],
    )

    print(f"[DONE] results={len(all_results)} payouts={len(all_payouts)}")


if __name__ == "__main__":
    main()
