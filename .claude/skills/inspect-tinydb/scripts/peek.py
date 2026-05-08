#!/usr/bin/env python3
"""Read-only peek tool for the garmin-coach TinyDB.

Usage:
    peek.py tables
    peek.py recent <table> [N]
    peek.py id <activityId>
    peek.py date <table> <YYYY-MM-DD>
    peek.py snapshot

DB path defaults to /data/garmin_coach.json. Override with GARMIN_COACH_DB_PATH.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DEFAULT_DB_PATH = "/data/garmin_coach.json"
DEFAULT_RECENT_N = 5
NOISY_FIELDS = ("splits", "hrZones", "summaryDTO", "geoPolylineDTO", "polyline")
SNAPSHOT_TABLES = (
    "fitness_metrics",
    "race_predictions",
    "lactate_threshold",
    "endurance_score",
)


def db_path() -> Path:
    return Path(os.environ.get("GARMIN_COACH_DB_PATH", DEFAULT_DB_PATH))


def load_db() -> dict:
    path = db_path()
    if not path.exists():
        sys.exit(
            f"DB not found at {path}. Set GARMIN_COACH_DB_PATH if running outside Docker."
        )
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def trim_record(rec: dict) -> dict:
    return {k: v for k, v in rec.items() if k not in NOISY_FIELDS}


def cmd_tables(db: dict) -> None:
    for table_name, rows in sorted(db.items()):
        print(f"{table_name}: {len(rows)}")


def _activity_sort_key(rec: dict) -> str:
    return rec.get("startTimeLocal") or rec.get("date") or ""


def cmd_recent(db: dict, table: str, n: int) -> None:
    rows = list(db.get(table, {}).values())
    if not rows:
        sys.exit(f"Table {table!r} empty or missing.")
    rows.sort(key=_activity_sort_key, reverse=True)
    for rec in rows[:n]:
        print(json.dumps(trim_record(rec), indent=2, ensure_ascii=False, default=str))


def cmd_id(db: dict, activity_id: str) -> None:
    for rec in db.get("activities", {}).values():
        if str(rec.get("activityId")) == str(activity_id):
            print(
                json.dumps(trim_record(rec), indent=2, ensure_ascii=False, default=str)
            )
            return
    sys.exit(f"No activity with id {activity_id} in DB.")


def cmd_date(db: dict, table: str, date_iso: str) -> None:
    rows = list(db.get(table, {}).values())
    if not rows:
        sys.exit(f"Table {table!r} empty or missing.")
    matched: list[dict] = []
    for rec in rows:
        candidate = (rec.get("startTimeLocal") or rec.get("date") or "")[:10]
        if candidate == date_iso:
            matched.append(rec)
    if not matched:
        sys.exit(f"No records on {date_iso} in {table}.")
    for rec in matched:
        print(json.dumps(trim_record(rec), indent=2, ensure_ascii=False, default=str))


def cmd_snapshot(db: dict) -> None:
    for table in SNAPSHOT_TABLES:
        rows = list(db.get(table, {}).values())
        if not rows:
            print(f"{table}: <empty>")
            continue
        latest = max(rows, key=lambda r: r.get("date", ""))
        print(f"{table}:")
        print(
            json.dumps(trim_record(latest), indent=2, ensure_ascii=False, default=str)
        )


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        sys.exit(__doc__)
    raw = load_db()
    # TinyDB JSON wraps tables under "_default" or named sections. Garmin-coach
    # uses named tables, so the top-level dict is {table: {row_id: record}}.
    db = raw

    cmd = argv[1]
    if cmd == "tables":
        cmd_tables(db)
    elif cmd == "recent":
        if len(argv) < 3:
            sys.exit("Usage: peek.py recent <table> [N]")
        n = int(argv[3]) if len(argv) > 3 else DEFAULT_RECENT_N
        cmd_recent(db, argv[2], n)
    elif cmd == "id":
        if len(argv) < 3:
            sys.exit("Usage: peek.py id <activityId>")
        cmd_id(db, argv[2])
    elif cmd == "date":
        if len(argv) < 4:
            sys.exit("Usage: peek.py date <table> <YYYY-MM-DD>")
        cmd_date(db, argv[2], argv[3])
    elif cmd == "snapshot":
        cmd_snapshot(db)
    else:
        sys.exit(f"Unknown command: {cmd}\n{__doc__}")


if __name__ == "__main__":
    main(sys.argv)
