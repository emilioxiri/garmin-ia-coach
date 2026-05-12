"""
services/sync_helpers.py
Pure helper functions for sync orchestration.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Callable, Iterator

from garmin_coach.app.logging_setup import get_logger

if TYPE_CHECKING:
    from garmin_coach.app.container import Repositories

logger = get_logger(__name__)


def daterange(start_iso: str, end_iso: str) -> Iterator[str]:
    """Yield YYYY-MM-DD strings from start_iso to end_iso inclusive."""
    current = date.fromisoformat(start_iso)
    end = date.fromisoformat(end_iso)
    while current <= end:
        yield current.isoformat()
        current += timedelta(days=1)


def compute_sync_window(
    repositories: "Repositories", default_days: int
) -> tuple[str, str]:
    """Return (start_iso, end_iso) for the sync window.

    If all data tables are empty → last default_days days.
    Otherwise → from the most recent date already in the DB until today.
    """
    today = date.today()

    activity_repo = repositories.activities
    sleep_repo = repositories.sleep
    hrv_repo = repositories.hrv
    body_battery_repo = repositories.body_battery

    is_empty = (
        activity_repo.is_empty()
        and sleep_repo.is_empty()
        and hrv_repo.is_empty()
        and body_battery_repo.is_empty()
    )

    if is_empty:
        start = today - timedelta(days=default_days)
        logger.info("DB empty — syncing last %d days from %s", default_days, start)
        return start.isoformat(), today.isoformat()

    dates: list[str] = []
    for act in activity_repo.all():
        s = act.get("startTimeLocal") or act.get("startTime", "")
        if s and len(s) >= 10:
            dates.append(s[:10])
    for repo in (sleep_repo, hrv_repo, body_battery_repo):
        for record in repo.all():
            d = record.get("date", "")
            if d:
                dates.append(d)

    last_date_str = (
        max(dates) if dates else (today - timedelta(days=default_days)).isoformat()
    )
    logger.info("DB not empty — syncing from %s (last DB record)", last_date_str)
    return last_date_str, today.isoformat()


def merge_activity_details(
    activities: list[dict],
    detail_fetcher: Callable[[str], dict | None],
) -> list[dict]:
    """Merge detailed metrics into each activity dict.

    detail_fetcher(activity_id) should return a dict (or None on failure).
    Merges top-level keys and flattens summaryDTO if present.
    Failures are non-fatal — the original activity dict is returned unchanged.
    """
    merged: list[dict] = []
    for act in activities:
        act_id = str(act.get("activityId", ""))
        record = dict(act)
        try:
            details = detail_fetcher(act_id)
            if details:
                for key, value in details.items():
                    if value is not None:
                        record[key] = value
                for key, value in details.get("summaryDTO", {}).items():
                    if value is not None:
                        record[key] = value
        except Exception as exc:
            logger.debug("Could not merge details for activity %s: %s", act_id, exc)
        merged.append(record)
    return merged
