#!/usr/bin/env python3
"""KRA 과거 경주 결과/배당 수집기."""

from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import random
import re
import time
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urljoin
from urllib.request import Request, urlopen


USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

BET_TYPES = ["단승식", "연승식", "복승식", "쌍승식", "복연승식", "삼복승식", "삼쌍승식"]
CODE_TO_MEET = {"1": "서울", "2": "부산경남", "3": "제주"}
MEET_TO_CODE = {v: k for k, v in CODE_TO_MEET.items()}


@dataclasses.dataclass
class RacePayout:
    race_date: str
    meet: str
    race_no: int
    bet_type: str
    combination: str
    odds: str
    raw_text: str = ""


@dataclasses.dataclass
class HorseResult:
    race_date: str
    meet: str
    race_no: int
    weather: str = ""
    track_condition: str = ""
    race_day_no: str = ""
    race_time: str = ""
    grade: str = ""
    distance_m: str = ""
    burden_type: str = ""
    race_name: str = ""
    rating_condition: str = ""
    age_sex_condition: str = ""
    rank: str = ""
    horse_no: int = 0
    horse_name: str = ""
    origin: str = ""
    sex: str = ""
    age: str = ""
    weight: str = ""
    rating: str = ""
    jockey: str = ""
    trainer: str = ""
    owner: str = ""
    margin: str = ""
    body_weight: str = ""
    win_odds: str = ""
    place_odds: str = ""
    equipment: str = ""


def _strip_tags(html: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def _extract_table_by_caption(html: str, caption_keyword: str) -> str:
    for m in re.finditer(r"<table\b.*?</table>", html, flags=re.IGNORECASE | re.DOTALL):
        block = m.group(0)
        cap = re.search(r"<caption\b[^>]*>(.*?)</caption>", block, flags=re.IGNORECASE | re.DOTALL)
        if cap and caption_keyword in _strip_tags(cap.group(1)):
            return block
    return ""


def normalize_meet(meet: str) -> str:
    s = str(meet).strip()
    if s in CODE_TO_MEET:
        return s
    if s in MEET_TO_CODE:
        return MEET_TO_CODE[s]
    raise ValueError(f"unknown meet: {meet}")


def daterange(start: dt.date, end: dt.date) -> Iterable[dt.date]:
    cursor = start
    while cursor <= end:
        yield cursor
        cursor += dt.timedelta(days=1)


def fetch_html(url: str, timeout: int = 20) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as res:
        return res.read().decode("utf-8", errors="replace")


def build_daily_url(meet_code: str, race_date: dt.date) -> str:
    return f"https://race.kra.co.kr/raceScore/ScoretableDetailList.do?meet={meet_code}&realRcDate={race_date:%Y%m%d}"


def build_detail_url(meet_code: str, rc_date_yyyymmdd: str, rc_no: str) -> str:
    return (
        "https://race.kra.co.kr/raceScore/ScoretableDetail.do"
        f"?meet={meet_code}&realRcDate={rc_date_yyyymmdd}&realRcNo={int(rc_no)}"
    )


def extract_race_keys_from_daily(html: str) -> list[tuple[str, str, str]]:
    keys: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for m in re.finditer(r"ScoreDetailPopup\('(\d)','(\d{8})','(\d+)'\)", html):
        key = (m.group(1), m.group(2), m.group(3))
        if key not in seen:
            seen.add(key)
            keys.append(key)
    return keys


def parse_race_meta(html: str, default_meet: str, default_date: str, default_race_no: int) -> dict[str, str]:
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

    top_row = re.search(r"<tr[^>]*class=\"alignC\"[^>]*>(.*?)</tr>", html, flags=re.IGNORECASE | re.DOTALL)
    if top_row:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", top_row.group(1), flags=re.IGNORECASE | re.DOTALL)
        if cells:
            line = _strip_tags(cells[0])
            m = re.search(r"(\d{4})년\s*(\d{2})월\s*(\d{2})일.*?제\s*(\d+)경주\s*(서울|부산경남|제주)", line)
            if m:
                meta["race_date"] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                meta["race_no"] = m.group(4)
                meta["meet"] = m.group(5)
        if len(cells) >= 2:
            meta["race_day_no"] = _strip_tags(cells[1])
        if len(cells) >= 3:
            meta["weather"] = _strip_tags(cells[2])
        if len(cells) >= 4:
            meta["track_condition"] = _strip_tags(cells[3])
        if len(cells) >= 1:
            meta["race_time"] = _strip_tags(cells[-1])

    second_rows = re.findall(r"<tr[^>]*class=\"alignC\"[^>]*>(.*?)</tr>", html, flags=re.IGNORECASE | re.DOTALL)
    if len(second_rows) >= 2:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", second_rows[1], flags=re.IGNORECASE | re.DOTALL)
        if len(cells) >= 1:
            meta["grade"] = _strip_tags(cells[0])
        if len(cells) >= 2:
            meta["distance_m"] = _strip_tags(cells[1])
        if len(cells) >= 3:
            meta["burden_type"] = _strip_tags(cells[2])
        if len(cells) >= 4:
            meta["race_name"] = _strip_tags(cells[3])
        if len(cells) >= 5:
            meta["rating_condition"] = _strip_tags(cells[4])
        if len(cells) >= 7:
            meta["age_sex_condition"] = _strip_tags(cells[6])
    return meta


def parse_horse_results(html: str, meta: dict[str, str]) -> list[HorseResult]:
    table = _extract_table_by_caption(html, "경주상세성적")
    if not table:
        return []
    tbody = re.search(r"<tbody[^>]*>(.*?)</tbody>", table, flags=re.IGNORECASE | re.DOTALL)
    if not tbody:
        return []

    out: list[HorseResult] = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tbody.group(1), flags=re.IGNORECASE | re.DOTALL):
        tds = [_strip_tags(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.IGNORECASE | re.DOTALL)]
        if len(tds) < 16:
            continue
        try:
            horse_no = int(tds[1]) if tds[1].isdigit() else 0
        except ValueError:
            horse_no = 0
        out.append(
            HorseResult(
                race_date=meta["race_date"],
                meet=meta["meet"],
                race_no=int(meta["race_no"]),
                weather=meta.get("weather", ""),
                track_condition=meta.get("track_condition", ""),
                race_day_no=meta.get("race_day_no", ""),
                race_time=meta.get("race_time", ""),
                grade=meta.get("grade", ""),
                distance_m=meta.get("distance_m", ""),
                burden_type=meta.get("burden_type", ""),
                race_name=meta.get("race_name", ""),
                rating_condition=meta.get("rating_condition", ""),
                age_sex_condition=meta.get("age_sex_condition", ""),
                rank=tds[0],
                horse_no=horse_no,
                horse_name=tds[2],
                origin=tds[3],
                sex=tds[4],
                age=tds[5],
                weight=tds[6],
                rating=tds[7],
                jockey=tds[8],
                trainer=tds[9],
                owner=tds[10],
                margin=tds[11],
                body_weight=tds[12],
                win_odds=tds[13],
                place_odds=tds[14],
                equipment=tds[15],
            )
        )
    return out


def _extract_pairs(raw_text: str) -> list[tuple[str, str]]:
    token = re.findall(r"([①-⑳]+|\d+(?:[-/]\d+)*|\S+)\s*([0-9]+(?:\.[0-9]+)?)", raw_text)
    return [(a.strip(), b.strip()) for a, b in token]


def _extract_odds_links(html: str, base_url: str = "https://race.kra.co.kr") -> list[str]:
    links: list[str] = []
    seen: set[str] = set()

    for href, label in re.findall(
        r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        label_text = _strip_tags(label)
        if "배당" in label_text or "odds" in href.lower():
            u = urljoin(base_url, href.strip())
            if u not in seen:
                seen.add(u)
                links.append(u)

    for raw_url in re.findall(
        r"(https?://[^'\"\s>]+|/[^'\"\s>]*odds[^'\"\s>]*)",
        html,
        flags=re.IGNORECASE,
    ):
        u = urljoin(base_url, raw_url.strip())
        if u not in seen:
            seen.add(u)
            links.append(u)

    return links


def _parse_payout_rows_from_html(html: str, meta: dict[str, str], seen: set[tuple[str, str, str]]) -> list[RacePayout]:
    table = _extract_table_by_caption(html, "배당률")
    payouts: list[RacePayout] = []
    source_html = table if table else html

    # 1) 표준 케이스: "단승식: ② 11.5" 처럼 bet_type이 같은 셀에 있는 경우
    for td in re.findall(r"<td[^>]*class=\"textLeft\"[^>]*>(.*?)</td>", source_html, flags=re.IGNORECASE | re.DOTALL):
        text = _strip_tags(td)
        m = re.match(r"^(단승식|연승식|복승식|쌍승식|복연승식|삼복승식|삼쌍승식)\s*:\s*(.*)$", text)
        if not m:
            continue
        bet_type, body = m.group(1), m.group(2).strip()

        pairs = _extract_pairs(body)
        for combination, odds in pairs:
            k = (bet_type, combination, odds)
            if k in seen:
                continue
            seen.add(k)
            payouts.append(
                RacePayout(
                    race_date=meta["race_date"],
                    meet=meta["meet"],
                    race_no=int(meta["race_no"]),
                    bet_type=bet_type,
                    combination=combination,
                    odds=odds,
                    raw_text=body,
                )
            )

    # 2) 확장 케이스: 링크된 배당 페이지에서 bet_type 제목과 배당 쌍이 분리되어 있는 경우
    flat = _strip_tags(source_html)
    bet_type_pat = "|".join(re.escape(x) for x in BET_TYPES)
    block_pat = re.compile(rf"({bet_type_pat})\s*:?\s*(.*?)(?=({bet_type_pat})\s*:?\s*|$)")
    for m in block_pat.finditer(flat):
        bet_type = m.group(1)
        body = m.group(2).strip()
        if not body:
            continue
        for combination, odds in _extract_pairs(body):
            k = (bet_type, combination, odds)
            if k in seen:
                continue
            seen.add(k)
            payouts.append(
                RacePayout(
                    race_date=meta["race_date"],
                    meet=meta["meet"],
                    race_no=int(meta["race_no"]),
                    bet_type=bet_type,
                    combination=combination,
                    odds=odds,
                    raw_text=body,
                )
            )
    return payouts


def parse_payouts(
    html: str,
    meta: dict[str, str],
    fetcher: Callable[[str], str] = fetch_html,
    base_url: str = "https://race.kra.co.kr",
) -> list[RacePayout]:
    seen: set[tuple[str, str, str]] = set()
    payouts = _parse_payout_rows_from_html(html, meta, seen)

    # 상세 페이지 배당은 "실현 배당" 위주이므로, 별도 배당 링크가 있으면 함께 수집한다.
    for odds_url in _extract_odds_links(html, base_url=base_url):
        try:
            odds_html = fetcher(odds_url)
        except Exception:  # noqa: BLE001
            continue
        payouts.extend(_parse_payout_rows_from_html(odds_html, meta, seen))
    return payouts


def parse_daily_page(_html: str, _race_date: dt.date, _meet: str) -> tuple[list[HorseResult], list[RacePayout]]:
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

    meet_code = normalize_meet(args.meet)
    for d in daterange(start, end):
        url = build_daily_url(meet_code, d)
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
