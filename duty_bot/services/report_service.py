import logging
from datetime import datetime
from typing import Any

import duty_bot.database.repository as repo

logger = logging.getLogger(__name__)

SHIFT_LABELS = {"sang": "Sáng"}


def weekly_report(year: int, week: int) -> str:
    from datetime import date as date_type
    week_start = date_type.fromisocalendar(year, week, 1)
    week_end = date_type.fromisocalendar(year, week, 7)

    schedules = repo.get_schedules_by_date_range(
        week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d")
    )

    if not schedules:
        return f"Tuần {week}/{year} không có lịch trực."

    weekdays = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]
    lines = [f"BÁO CÁO LỊCH TRỰC TUẦN {week}/{year}"]
    lines.append(f"({week_start.strftime('%d/%m/%Y')} - {week_end.strftime('%d/%m/%Y')})")
    lines.append("")

    current_date = None
    for s in schedules:
        d = datetime.strptime(s["date"], "%Y-%m-%d")
        date_label = f"{d.strftime('%d/%m/%Y')} ({weekdays[d.weekday()]})"
        if date_label != current_date:
            current_date = date_label
            lines.append(f"  {date_label}:")
        shift_label = SHIFT_LABELS.get(s["shift"], s["shift"])
        status_icon = ""
        if s["status"] == "approved":
            status_icon = " ✅"
        elif s["status"] == "pending_approval":
            status_icon = " ⏳"
        elif s["status"] == "draft":
            status_icon = " 📝"
        lines.append(f"    - {s.get('personnel_name', '?')} (ca {shift_label}){status_icon}")

    lines.append("")
    lines.append(f"Tổng: {len(schedules)} ca trực")
    return "\n".join(lines)


def monthly_report(year: int, month: int) -> str:
    import calendar
    num_days = calendar.monthrange(year, month)[1]
    start = f"{year:04d}-{month:02d}-01"
    end = f"{year:04d}-{month:02d}-{num_days:02d}"

    schedules = repo.get_schedules_by_date_range(start, end)
    if not schedules:
        return f"Tháng {month}/{year} không có lịch trực."

    lines = [f"BÁO CÁO LỊCH TRỰC THÁNG {month}/{year}", ""]

    current_date = None
    for s in schedules:
        d = datetime.strptime(s["date"], "%Y-%m-%d")
        date_label = d.strftime("%d/%m/%Y")
        if date_label != current_date:
            current_date = date_label
        shift_label = SHIFT_LABELS.get(s["shift"], s["shift"])
        lines.append(f"  {date_label}: {s.get('personnel_name', '?')} (ca {shift_label})")

    lines.append("")
    lines.append(f"Tổng: {len(schedules)} ca trực")

    stats = repo.get_personnel_shift_count(start, end)
    if stats:
        lines.append("")
        lines.append("Thống kê theo CBCS:")
        for s in stats:
            lines.append(f"  - {s['name']}: {s['shift_count']} ca")

    return "\n".join(lines)


def personnel_stats(start_date: str, end_date: str) -> dict[str, Any]:
    stats = repo.get_personnel_shift_count(start_date, end_date)
    if not stats:
        return {"stats": [], "most": None, "least": None, "total": 0}

    total = sum(s["shift_count"] for s in stats)
    most = stats[0] if stats else None
    least = stats[-1] if stats else None

    return {
        "stats": stats,
        "most": most,
        "least": least,
        "total": total,
    }


def export_to_text(report_data: str) -> str:
    return report_data
