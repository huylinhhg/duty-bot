import logging
from datetime import datetime, time, timedelta

import pytz
from telegram.ext import Application, ContextTypes

from duty_bot.config import CHAT_IDS, TIMEZONE, get_holiday_dates
from duty_bot.services import scheduler_service, report_service, notification_service
import duty_bot.database.repository as repo

logger = logging.getLogger(__name__)


_holiday_cache: dict[int, set[str]] = {}


def _is_non_duty_day(date_obj: datetime) -> bool:
    """Check if date is weekend (Fri-Sun) or holiday."""
    if date_obj.weekday() >= 5:  # T7=5, CN=6
        return True
    year = date_obj.year
    if year not in _holiday_cache:
        _holiday_cache[year] = get_holiday_dates(year)
    return date_obj.strftime("%Y-%m-%d") in _holiday_cache[year]


def _find_next_duty(from_date: datetime) -> datetime:
    d = from_date
    while _is_non_duty_day(d):
        d += timedelta(days=1)
    return d


async def daily_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_ids = [c.strip() for c in CHAT_IDS.split(",") if c.strip()]
    if not chat_ids:
        return

    today = datetime.today()
    tomorrow = today + timedelta(days=1)

    today_str = today.strftime("%Y-%m-%d")
    today_display = today.strftime("%d/%m")

    def name_for_date(date_str: str) -> str:
        rows = scheduler_service.get_schedules_by_date(date_str)
        return rows[0].get("personnel_name", "?") if rows else "?"

    today_name = name_for_date(today_str)
    msg_parts = [
        f"Lịch trực hôm nay ({today_display}): {today_name}",
    ]

    if _is_non_duty_day(tomorrow):
        next_duty = _find_next_duty(tomorrow)
        next_display = next_duty.strftime("%d/%m")
        next_name = name_for_date(next_duty.strftime("%Y-%m-%d"))
        msg_parts.append(f"Ngày trực tiếp theo ({next_display}): {next_name}")
    else:
        tomorrow_str = tomorrow.strftime("%Y-%m-%d")
        tomorrow_display = tomorrow.strftime("%d/%m")
        tomorrow_name = name_for_date(tomorrow_str)
        msg_parts.append(f"Ngày mai ({tomorrow_display}): {tomorrow_name}")

    msg = "\n".join(msg_parts)
    for cid in chat_ids:
        try:
            await context.bot.send_message(chat_id=int(cid), text=msg)
            logger.info("Reminder sent to %s", cid)
        except Exception as e:
            logger.error("Failed to send reminder to %s: %s", cid, e)


async def weekly_start_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    today = datetime.today()
    weekday = today.weekday()
    if weekday >= 5:  # T7-CN: không gửi
        return

    # Chỉ gửi nếu hôm qua là ngày không trực (tức hôm nay là đầu tuần)
    prev = today - timedelta(days=1)
    if not _is_non_duty_day(prev):
        # Hôm qua vẫn là ngày trực → không phải đầu tuần
        return

    if _is_non_duty_day(today):
        return

    chat_ids = [c.strip() for c in CHAT_IDS.split(",") if c.strip()]
    if not chat_ids:
        return

    iso = today.isocalendar()
    week_number = iso[1]
    schedules = scheduler_service.get_week_schedules(iso[0], week_number)
    if not schedules:
        return

    msg_parts = [f"LỊCH TRỰC TUẦN {week_number}/{iso[0]}"]
    for s in schedules:
        d = datetime.strptime(s["date"], "%Y-%m-%d")
        date_label = d.strftime("%d/%m")
        name = s.get("personnel_name", "?")
        msg_parts.append(f"  {date_label}: {name}")

    msg = "\n".join(msg_parts)
    for cid in chat_ids:
        try:
            await context.bot.send_message(chat_id=int(cid), text=msg)
            logger.info("Weekly start reminder sent to %s", cid)
        except Exception as e:
            logger.error("Failed to send weekly start reminder to %s: %s", cid, e)


async def weekly_approval_check(context: ContextTypes.DEFAULT_TYPE) -> None:
    today = datetime.today()
    next_monday = today + timedelta(days=(7 - today.weekday()))
    next_sunday = next_monday + timedelta(days=6)
    week_start = next_monday.strftime("%Y-%m-%d")
    week_end = next_sunday.strftime("%Y-%m-%d")

    schedules = scheduler_service.get_schedules_by_date_range(week_start, week_end)
    if not schedules:
        logger.info("No schedules for next week %s", week_start)
        return

    chat_ids = [c.strip() for c in CHAT_IDS.split(",") if c.strip()]
    if not chat_ids:
        return

    msg_parts = [f"Lịch trực tuần sau ({week_start} - {week_end}):"]
    for s in schedules:
        msg_parts.append(f"- {s['date']}: {s.get('personnel_name', '?')}")
    msg_parts.append("\nDùng /submit_approval để gửi duyệt.")
    msg = "\n".join(msg_parts)

    for cid in chat_ids:
        try:
            await context.bot.send_message(chat_id=int(cid), text=msg)
            logger.info("Weekly approval check sent to %s", cid)
        except Exception as e:
            logger.error("Failed to send weekly check to %s: %s", cid, e)


async def retry_failed_notifications(context: ContextTypes.DEFAULT_TYPE) -> None:
    pending = notification_service.get_pending_notifications()
    if not pending:
        return

    for notif in pending:
        async def send_func(chat_id: int, text: str):
            await context.bot.send_message(chat_id=chat_id, text=text)

        await notification_service.send_with_retry(notif["id"], send_func)
        logger.info("Retried notification id=%d", notif["id"])


def setup_jobs(app: Application) -> None:
    tz = pytz.timezone(TIMEZONE)

    job_queue = app.job_queue
    if not job_queue:
        logger.warning("No job queue available")
        return

    job_queue.run_daily(daily_reminder, time=time(15, 0), days=tuple(range(7)), name="daily_reminder")
    job_queue.run_daily(weekly_start_reminder, time=time(9, 0), days=tuple(range(7)), name="weekly_start_reminder")
    job_queue.run_daily(weekly_approval_check, time=time(18, 0), days=(4,), name="weekly_approval_check")
    job_queue.run_repeating(retry_failed_notifications, interval=1800, first=10, name="retry_notifications")

    logger.info("Jobs setup complete")
