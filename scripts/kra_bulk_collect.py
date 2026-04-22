#!/usr/bin/env python3
"""대용량(장기간) KRA 데이터 수집기.

기존 `kra_results_crawler.py`의 파서를 재사용하고,
- 메모리 누수 없이 즉시 CSV append
- 체크포인트(json) 저장/재개
- --meet all 지원
을 제공한다.
"""

from __future__ import annotations

import argparse
import sys
import csv
import dataclasses
import datetime as dt
import json
import random
import time
from pathlib import Path
from datetime import datetime, timezone

sys.path.append(str(Path(__file__).resolve().parent))

from kra_results_crawler import (
    CODE_TO_MEET,
    HorseResult,
    RacePayout,
    build_daily_url,
    build_detail_url,
    extract_race_keys_from_daily,
    fetch_html,
    normalize_meet,
    parse_horse_results,
    parse_payouts,
    parse_race_meta,
)


def ensure_csv_header(path: Path, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()


def append_rows(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    if not rows:
        return
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writerows(rows)


def load_checkpoint(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_checkpoint(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_meets(meet_arg: str) -> list[str]:
    if meet_arg.lower() == "all":
        return ["1", "2", "3"]
    return [normalize_meet(meet_arg)]




def date_desc_range(start: dt.date, end: dt.date):
    cur = end
    while cur >= start:
        yield cur
        cur -= dt.timedelta(days=1)




def append_report(report_file: Path | None, message: str) -> None:
    if report_file is None:
        return
    report_file.parent.mkdir(parents=True, exist_ok=True)
    with report_file.open("a", encoding="utf-8") as f:
        f.write(message + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default="2000-01-01", help="YYYY-MM-DD")
    parser.add_argument("--end-date", default=dt.date.today().isoformat(), help="YYYY-MM-DD")
    parser.add_argument("--meet", default="all", help="서울|부산경남|제주|1|2|3|all")
    parser.add_argument("--out-results", default="data/full/race_results_full.csv")
    parser.add_argument("--out-payouts", default="data/full/race_payouts_full.csv")
    parser.add_argument("--checkpoint", default="data/full/checkpoint.json")
    parser.add_argument("--sleep-min", type=float, default=0.05)
    parser.add_argument("--sleep-max", type=float, default=0.2)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--report-interval-sec", type=int, default=3600, help="진행 보고 간격(초), 기본 3600")
    parser.add_argument("--report-file", default="", help="진행 보고 로그 파일 경로(선택)")
    args = parser.parse_args()

    start = dt.datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end = dt.datetime.strptime(args.end_date, "%Y-%m-%d").date()
    meets = resolve_meets(args.meet)

    out_results = Path(args.out_results)
    out_payouts = Path(args.out_payouts)
    ckpt_path = Path(args.checkpoint)

    result_fields = [f.name for f in dataclasses.fields(HorseResult)]
    payout_fields = [f.name for f in dataclasses.fields(RacePayout)]
    ensure_csv_header(out_results, result_fields)
    ensure_csv_header(out_payouts, payout_fields)

    ckpt = load_checkpoint(ckpt_path) if args.resume else {}
    ckpt.setdefault("last_done", {})

    total_results = 0
    total_payouts = 0
    report_file = Path(args.report_file) if args.report_file else None
    last_report_ts = time.time()

    for meet_code in meets:
        meet_name = CODE_TO_MEET[meet_code]
        meet_end = end
        if args.resume and (meet_code in ckpt["last_done"]):
            done_day = dt.datetime.strptime(ckpt["last_done"][meet_code], "%Y-%m-%d").date()
            meet_end = min(end, done_day - dt.timedelta(days=1))

        print(f"[MEET] {meet_name} ({meet_code}) from {meet_end} down to {start}")

        for d in date_desc_range(start, meet_end):
            try:
                daily_html = fetch_html(build_daily_url(meet_code, d))
                race_keys = extract_race_keys_from_daily(daily_html)
            except Exception as e:  # noqa: BLE001
                print(f"[WARN] daily fail {meet_name} {d}: {e}")
                continue

            day_results = 0
            day_payouts = 0

            for mk, rc_date, rc_no in race_keys:
                try:
                    detail_html = fetch_html(build_detail_url(mk, rc_date, rc_no))
                    default_date = f"{rc_date[:4]}-{rc_date[4:6]}-{rc_date[6:8]}"
                    meta = parse_race_meta(detail_html, meet_name, default_date, int(rc_no))
                    results = parse_horse_results(detail_html, meta)
                    payouts = parse_payouts(detail_html, meta)
                    append_rows(out_results, [dataclasses.asdict(x) for x in results], result_fields)
                    append_rows(out_payouts, [dataclasses.asdict(x) for x in payouts], payout_fields)
                    day_results += len(results)
                    day_payouts += len(payouts)
                except Exception as e:  # noqa: BLE001
                    print(f"[WARN] detail fail {meet_name} {rc_date}-{rc_no}: {e}")

                time.sleep(random.uniform(args.sleep_min, args.sleep_max))

            # 최근일자 -> 과거일자 순으로 처리하므로, 마지막 처리일을 저장
            ckpt["last_done"][meet_code] = d.isoformat()
            save_checkpoint(ckpt_path, ckpt)

            if race_keys:
                print(f"[OK] {meet_name} {d} races={len(race_keys)} results={day_results} payouts={day_payouts}")

            total_results += day_results
            total_payouts += day_payouts

            now_ts = time.time()
            if args.report_interval_sec > 0 and (now_ts - last_report_ts) >= args.report_interval_sec:
                msg = (
                    f"[REPORT] {datetime.now(timezone.utc).isoformat()} "
                    f"meet={meet_name} last_day={d} total_results={total_results} total_payouts={total_payouts}"
                )
                print(msg)
                append_report(report_file, msg)
                last_report_ts = now_ts

    done_msg = f"[DONE] appended results={total_results} payouts={total_payouts}"
    print(done_msg)
    append_report(report_file, done_msg)


if __name__ == "__main__":
    main()
