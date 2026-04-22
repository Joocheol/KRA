#!/usr/bin/env python3
"""KRA 과거 경주 결과/배당 수집기.

- 경주 목록: /raceScore/ScoretableDailyList.do
- 경주 상세: /raceScore/ScoretableDetailList.do

출력:
1) race_results.csv : 말 단위 결과(경주 메타 포함)
2) race_payouts.csv : 승식/조합 단위 배당 (모든 승식 행 정규화)
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import html as ihtml
import random
import re
import time
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

MEET_TO_CODE = {
    "1": "1",
    "2": "2",
    "3": "3",
    "서울": "1",
    "제주": "2",
    "부산": "3",
    "부산경남": "3",
}
CODE_TO_MEET = {"1": "서울", "2": "제주", "3": "부산경남"}

BET_TYPES = ["단승식", "연승식", "복승식", "쌍승식", "복연승식", "삼복승식", "삼쌍승식"]


@dataclasses.dataclass
class RacePayout:
    race_date: str
    meet: str
    race_no: int
    bet_type: str
    combination: str
    odds: str
    raw_text: str


@dataclasses.dataclass
class HorseResult:
    race_date: str
    meet: str
    race_no: int
    weather: str
    track_condition: str
    race_day_no: str
    race_time: str
    grade: str
    distance_m: str
    burden_type: str
    race_name: str
    rating_condition: str
    age_sex_condition: str
    rank: str
    horse_no: str
    horse_name: str
    origin: str
    sex: str
    age: str
    weight: str
    rating: str
    jockey: str
    trainer: str
    owner: str
    margin: str
    body_weight: str
    win_odds: str
    place_odds: str
    equipment: str


def daterange(start: dt.date, end: dt.date) -> Iterable[dt.date]:
    cur = start
    while cur <= end:
        yield cur
        cur += dt.timedelta(days=1)


def strip_tags(s: str) -> str:
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = ihtml.unescape(s)
    s = s.replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def fetch_html(url: str, timeout: int = 30, retries: int = 3) -> str:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        req = Request(url, headers={"User-Agent": USER_AGENT, "Referer": "https://race.kra.co.kr/"})
        try:
            with urlopen(req, timeout=timeout) as res:
                raw = res.read()
            # 사이트가 EUC-KR 기반
            return raw.decode("euc-kr", errors="ignore")
        except (HTTPError, URLError, TimeoutError) as e:
            last_error = e
            if attempt == retries:
                break
            time.sleep(min(5, 0.8 * (2**attempt)) + random.uniform(0.0, 0.5))
    raise RuntimeError(f"요청 실패: {url} / {last_error}")


def build_daily_url(meet_code: str, race_date: dt.date) -> str:
    return (
        "https://race.kra.co.kr/raceScore/ScoretableDailyList.do"
        f"?meet={meet_code}&realRcDate={race_date.strftime('%Y%m%d')}"
    )


def build_detail_url(meet_code: str, real_rc_date: str, real_rc_no: str) -> str:
    return (
        "https://race.kra.co.kr/raceScore/ScoretableDetailList.do"
        f"?meet={meet_code}&realRcDate={real_rc_date}&realRcNo={real_rc_no}"
    )


def extract_race_keys_from_daily(html: str) -> list[tuple[str, str, str]]:
    keys = re.findall(r"ScoreDetailPopup\('(\d+)','(\d{8})','(\d+)'\)", html)
    seen: set[tuple[str, str, str]] = set()
    out: list[tuple[str, str, str]] = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def extract_table_by_caption_keyword(html: str, keyword: str) -> str | None:
    for table in re.findall(r"<table[^>]*>.*?</table>", html, flags=re.S | re.I):
        if keyword in table:
            return table
    return None


def parse_table_rows(table_html: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, flags=re.S | re.I):
        cells = re.findall(r"<(?:th|td)[^>]*>(.*?)</(?:th|td)>", tr, flags=re.S | re.I)
        rows.append([strip_tags(c) for c in cells])
    return rows


def parse_race_meta(detail_html: str, default_meet: str, default_date: str, default_race_no: int) -> dict[str, str]:
    table = extract_table_by_caption_keyword(detail_html, "경주정보중")
    if not table:
        # 캡션이 주석인 경우 fallback
        table = re.search(r"<table>\s*<!--<caption>경주정보중.*?</table>", detail_html, flags=re.S)
        table = table.group(0) if table else None
    meta = {
        "race_date": default_date,
        "meet": default_meet,
        "race_no": str(default_race_no),
        "race_day_no": "",
        "weather": "",
        "track_condition": "",
        "race_time": "",
        "grade": "",
        "distance_m": "",
        "burden_type": "",
        "race_name": "",
        "rating_condition": "",
        "age_sex_condition": "",
    }
    if not table:
        return meta

    rows = parse_table_rows(table)
    if len(rows) >= 1:
        first = rows[0]
        first_text = first[0] if first else ""
        m = re.search(r"(\d{4})년\s*(\d{2})월\s*(\d{2})일.*?제\s*(\d+)경주\s*(서울|부산|부산경남|제주)", first_text)
        if m:
            y, mo, d, race_no, meet = m.groups()
            meta["race_date"] = f"{y}-{mo}-{d}"
            meta["race_no"] = race_no
            meta["meet"] = meet
        if len(first) >= 4:
            meta["race_day_no"] = first[1] if len(first) > 1 else ""
            meta["weather"] = first[2] if len(first) > 2 else ""
            meta["track_condition"] = first[3] if len(first) > 3 else ""
            meta["race_time"] = first[5] if len(first) > 5 else ""

    if len(rows) >= 2:
        second = rows[1]
        if len(second) >= 7:
            meta["grade"] = second[0]
            meta["distance_m"] = second[1]
            meta["burden_type"] = second[2]
            meta["race_name"] = second[3]
            meta["rating_condition"] = second[4]
            meta["age_sex_condition"] = second[5]

    return meta


def parse_horse_results(detail_html: str, meta: dict[str, str]) -> list[HorseResult]:
    table = extract_table_by_caption_keyword(detail_html, "경주상세성적")
    if not table:
        return []

    rows = parse_table_rows(table)
    if len(rows) < 2:
        return []

    header = rows[0]
    out: list[HorseResult] = []
    for r in rows[1:]:
        if not r or not r[0]:
            continue
        # 컬럼 누락에 대비한 안전 패딩
        vals = r + [""] * (16 - len(r))
        row = dict(zip(header, vals))
        out.append(
            HorseResult(
                race_date=meta["race_date"],
                meet=meta["meet"],
                race_no=int(meta["race_no"]),
                weather=meta["weather"],
                track_condition=meta["track_condition"],
                race_day_no=meta["race_day_no"],
                race_time=meta["race_time"],
                grade=meta["grade"],
                distance_m=meta["distance_m"],
                burden_type=meta["burden_type"],
                race_name=meta["race_name"],
                rating_condition=meta["rating_condition"],
                age_sex_condition=meta["age_sex_condition"],
                rank=row.get("순위", ""),
                horse_no=row.get("마번", ""),
                horse_name=row.get("마명", ""),
                origin=row.get("산지", ""),
                sex=row.get("성별", ""),
                age=row.get("연령", ""),
                weight=row.get("중량", ""),
                rating=row.get("레이팅", ""),
                jockey=row.get("기수명", ""),
                trainer=row.get("조교사명", ""),
                owner=row.get("마주명", ""),
                margin=row.get("도착차", ""),
                body_weight=row.get("마체중", ""),
                win_odds=row.get("단승", ""),
                place_odds=row.get("연승", ""),
                equipment=row.get("장구현황", ""),
            )
        )
    return out


def parse_payouts(detail_html: str, meta: dict[str, str]) -> list[RacePayout]:
    table = extract_table_by_caption_keyword(detail_html, "배당률의 정보를 제공하는 표")
    if not table:
        return []

    rows = parse_table_rows(table)
    out: list[RacePayout] = []

    for r in rows:
        for cell in r:
            if ":" not in cell:
                continue
            bet_type, payload = [x.strip() for x in cell.split(":", 1)]
            if bet_type not in BET_TYPES:
                continue

            pairs = re.findall(r"([①-⑳]+)\s*([0-9]+(?:\.[0-9]+)?)", payload)
            if not pairs:
                out.append(
                    RacePayout(
                        race_date=meta["race_date"],
                        meet=meta["meet"],
                        race_no=int(meta["race_no"]),
                        bet_type=bet_type,
                        combination="",
                        odds="",
                        raw_text=payload,
                    )
                )
                continue

            for combination, odds in pairs:
                out.append(
                    RacePayout(
                        race_date=meta["race_date"],
                        meet=meta["meet"],
                        race_no=int(meta["race_no"]),
                        bet_type=bet_type,
                        combination=combination,
                        odds=odds,
                        raw_text=payload,
                    )
                )

    return out


def write_csv(path: str, rows: list[dict], fieldnames: list[str]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_meet(raw: str) -> str:
    if raw not in MEET_TO_CODE:
        raise ValueError(f"지원하지 않는 meet: {raw} (허용: {', '.join(sorted(MEET_TO_CODE))})")
    return MEET_TO_CODE[raw]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--meet", required=True, help="서울|부산경남|제주 또는 1|2|3")
    parser.add_argument("--out-results", default="data/race_results.csv")
    parser.add_argument("--out-payouts", default="data/race_payouts.csv")
    parser.add_argument("--sleep-min", type=float, default=0.4)
    parser.add_argument("--sleep-max", type=float, default=1.0)
    args = parser.parse_args()

    start = dt.datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end = dt.datetime.strptime(args.end_date, "%Y-%m-%d").date()
    meet_code = normalize_meet(args.meet)
    meet_name = CODE_TO_MEET[meet_code]

    all_results: list[HorseResult] = []
    all_payouts: list[RacePayout] = []

    for d in daterange(start, end):
        daily_url = build_daily_url(meet_code, d)
        print(f"[INFO] Daily {d} -> {daily_url}")

        try:
            daily_html = fetch_html(daily_url)
            race_keys = extract_race_keys_from_daily(daily_html)
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] 일별 목록 수집 실패 {d}: {e}")
            continue

        if not race_keys:
            print(f"[INFO] {d} 경주 없음")
            continue

        for mk, rc_date, rc_no in race_keys:
            detail_url = build_detail_url(mk, rc_date, rc_no)
            try:
                detail_html = fetch_html(detail_url)
                default_date = f"{rc_date[:4]}-{rc_date[4:6]}-{rc_date[6:8]}"
                meta = parse_race_meta(detail_html, meet_name, default_date, int(rc_no))
                results = parse_horse_results(detail_html, meta)
                payouts = parse_payouts(detail_html, meta)
                all_results.extend(results)
                all_payouts.extend(payouts)
                print(
                    f"  [OK] {meta['race_date']} {meta['meet']} R{meta['race_no']} "
                    f"results={len(results)} payouts={len(payouts)}"
                )
            except Exception as e:  # noqa: BLE001
                print(f"  [WARN] 상세 수집 실패 {rc_date}-{rc_no}: {e}")

            time.sleep(random.uniform(args.sleep_min, args.sleep_max))

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
