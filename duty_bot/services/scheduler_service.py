import calendar
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import duty_bot.database.repository as repo
from duty_bot.models.entities import DutySchedule

logger = logging.getLogger(__name__)

from duty_bot.config import get_holiday_dates

WEEKLY_SHIFTS = {
    0: ["sang"],  # T2
    1: ["sang"],  # T3
    2: ["sang"],  # T4
    3: ["sang"],  # T5
    # T6, T7, CN: không trực
}

SHIFT_LABELS = {"sang": "Sáng"}


_holiday_cache: dict[int, set[str]] = {}


def _is_holiday(date_obj: datetime) -> bool:
    year = date_obj.year
    if year not in _holiday_cache:
        _holiday_cache[year] = get_holiday_dates(year)
    return date_obj.strftime("%Y-%m-%d") in _holiday_cache[year]


def _get_next_weekday_date(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day)


def generate_monthly_schedule(
    year: int, month: int, skip_consecutive_days: bool = True
) -> dict[str, Any]:
    personnel_list = repo.get_active_personnel()
    if not personnel_list:
        return {"error": "Không có CBCS nào đang hoạt động", "schedules": [], "total": 0}

    num_days = calendar.monthrange(year, month)[1]
    personnel_ids = [p["id"] for p in personnel_list]
    n = len(personnel_ids)

    date_exclusions: dict[str, set[int]] = {}
    for pid in personnel_ids:
        exclusions = repo.get_exclusions(
            pid,
            f"{year:04d}-{month:02d}-01",
            f"{year:04d}-{month:02d}-{num_days:02d}",
        )
        for e in exclusions:
            start = datetime.strptime(e["start_date"], "%Y-%m-%d")
            end = datetime.strptime(e["end_date"], "%Y-%m-%d")
            d = start
            while d <= end:
                ds = d.strftime("%Y-%m-%d")
                if ds not in date_exclusions:
                    date_exclusions[ds] = set()
                date_exclusions[ds].add(pid)
                d += timedelta(days=1)

    group_name = personnel_list[0]["group_name"] or "default"
    rotation: dict[str, int] = {}
    for shift in ["sang"]:
        state = repo.get_rotation_state(group_name, shift)
        rotation[shift] = state["last_position"] if state else 0

    prev_day_assignments: set[int] = set()
    schedules_created: list[dict[str, Any]] = []

    for day in range(1, num_days + 1):
        date_obj = datetime(year, month, day)
        date_str = date_obj.strftime("%Y-%m-%d")
        weekday = date_obj.weekday()

        if _is_holiday(date_obj):
            continue

        today_excluded = date_exclusions.get(date_str, set())
        today_shifts = WEEKLY_SHIFTS.get(weekday, [])
        if not today_shifts:
            continue
        today_assignments: set[int] = set()

        for shift in today_shifts:
            pos = rotation.get(shift, 0)
            assigned = False

            for _ in range(n * 2):
                pid = personnel_ids[pos % n]
                pos += 1

                if pid in today_excluded:
                    continue
                if pid in today_assignments:
                    continue
                if skip_consecutive_days and pid in prev_day_assignments:
                    continue

                week_num = date_obj.isocalendar()[1]
                try:
                    repo.add_schedule(
                        date=date_str,
                        shift=shift,
                        personnel_id=pid,
                        group_name=group_name,
                        status="draft",
                        source="auto",
                        week_number=week_num,
                    )
                    schedules_created.append({
                        "personnel_id": pid,
                        "date": date_str,
                        "shift": shift,
                    })
                    today_assignments.add(pid)
                    rotation[shift] = pos % n
                    assigned = True
                except Exception as e:
                    logger.error("Failed to create schedule: %s", e)
                break

            if not assigned:
                logger.debug("No eligible person for %s shift %s", date_str, shift)

        prev_day_assignments = today_assignments

    for shift, pos in rotation.items():
        repo.set_rotation_state(group_name, shift, pos)

    audit_payload = json.dumps({"year": year, "month": month, "total": len(schedules_created)}, ensure_ascii=False)
    repo.add_audit_log("generate_monthly", "schedule", None, audit_payload)
    logger.info("Generated %d schedules for %d/%d", len(schedules_created), month, year)

    return {"schedules": schedules_created, "total": len(schedules_created)}


def generate_weekly_schedule(year: int, week: int) -> dict[str, Any]:
    from datetime import date as date_type
    week_start = date_type.fromisocalendar(year, week, 1)
    week_end = date_type.fromisocalendar(year, week, 7)
    month = week_start.month

    personnel_list = repo.get_active_personnel()
    if not personnel_list:
        return {"error": "Không có CBCS nào đang hoạt động", "schedules": [], "total": 0}

    personnel_ids = [p["id"] for p in personnel_list]
    n = len(personnel_ids)

    date_exclusions: dict[str, set[int]] = {}
    for pid in personnel_ids:
        exclusions = repo.get_exclusions(
            pid,
            week_start.strftime("%Y-%m-%d"),
            week_end.strftime("%Y-%m-%d"),
        )
        for e in exclusions:
            start = datetime.strptime(e["start_date"], "%Y-%m-%d")
            end = datetime.strptime(e["end_date"], "%Y-%m-%d")
            d = start
            while d <= end:
                ds = d.strftime("%Y-%m-%d")
                if ds not in date_exclusions:
                    date_exclusions[ds] = set()
                date_exclusions[ds].add(pid)
                d += timedelta(days=1)

    group_name = personnel_list[0]["group_name"] or "default"
    rotation: dict[str, int] = {}
    for shift in ["sang"]:
        state = repo.get_rotation_state(group_name, shift)
        rotation[shift] = state["last_position"] if state else 0

    prev_day_assignments: set[int] = set()
    schedules_created: list[dict[str, Any]] = []
    current = week_start

    while current <= week_end:
        date_str = current.strftime("%Y-%m-%d")
        weekday = current.weekday()

        if _is_holiday(current):
            current += timedelta(days=1)
            continue

        today_excluded = date_exclusions.get(date_str, set())
        today_shifts = WEEKLY_SHIFTS.get(weekday, [])
        if not today_shifts:
            current += timedelta(days=1)
            continue
        today_assignments: set[int] = set()

        for shift in today_shifts:
            pos = rotation.get(shift, 0)
            assigned = False
            for _ in range(n * 2):
                pid = personnel_ids[pos % n]
                pos += 1
                if pid in today_excluded:
                    continue
                if pid in today_assignments:
                    continue
                try:
                    repo.add_schedule(
                        date=date_str,
                        shift=shift,
                        personnel_id=pid,
                        group_name=group_name,
                        status="draft",
                        source="auto",
                        week_number=week,
                    )
                    schedules_created.append({
                        "personnel_id": pid,
                        "date": date_str,
                        "shift": shift,
                    })
                    today_assignments.add(pid)
                    rotation[shift] = pos % n
                    assigned = True
                except Exception as e:
                    logger.error("Failed to create schedule: %s", e)
                break
            if not assigned:
                logger.debug("No eligible person for %s shift %s", date_str, shift)

        prev_day_assignments = today_assignments
        current += timedelta(days=1)

    for shift, pos in rotation.items():
        repo.set_rotation_state(group_name, shift, pos)

    audit_payload = json.dumps({"year": year, "week": week, "total": len(schedules_created)}, ensure_ascii=False)
    repo.add_audit_log("generate_weekly", "schedule", None, audit_payload)
    logger.info("Generated %d schedules for week %d/%d", len(schedules_created), week, year)

    return {"schedules": schedules_created, "total": len(schedules_created)}


def get_week_schedules(year: int, week: int) -> list[dict[str, Any]]:
    return repo.get_week_schedules(year, week)


def get_schedules_by_date(date_str: str) -> list[dict[str, Any]]:
    return repo.get_schedules_by_date(date_str)


def get_schedules_by_date_range(start_date: str, end_date: str) -> list[dict[str, Any]]:
    return repo.get_schedules_by_date_range(start_date, end_date)


def get_pending_approval_week() -> list[dict[str, Any]]:
    return repo.get_pending_approval_weeks()


def get_all_future_schedules() -> list[dict[str, Any]]:
    today = datetime.today().strftime("%Y-%m-%d")
    all_s = repo.get_all_schedules()
    return [s for s in all_s if s["date"] >= today]
