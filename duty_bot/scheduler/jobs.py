import logging
from datetime import datetime, time, timedelta

import pytz
from telegram.ext import Application, ContextTypes

from duty_bot.config import CHAT_IDS, TIMEZONE, VIETNAM_HOLIDAYS
from duty_bot.services import scheduler_service, report_service, notification_service
import duty_bot.database.repository as repo

logger = logging.getLogger(__name__)


def _is_non_duty_day(date_obj: datetime) -> bool:
    """Check if date is weekend (Fri-Sun) or holiday."""
    if date_obj.weekday() >= 4:  # T6=4, T7=5, CN=6
        return True
    if (date_obj.month, date_obj.day) in VIETNAM_HOLIDAYS:
        return True
    return False


async def daily_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_ids = [c.strip() for c in CHAT_IDS.split(",") if c.strip()]
    if not chat_ids:
        return

    tomorrow = datetime.today() + timedelta(days=1)
    tomorrow_str = tomorrow.strftime("%Y-%m-%d")
    tomorrow_display = tomorrow.strftime("%d/%m")

    if _is_non_duty_day(tomorrow):
        # Tìm ngày trực tiếp theo (bỏ qua cuối tuần và lễ)
        next_duty = tomorrow
        while _is_non_duty_day(next_duty):
            next_duty += timedelta(days=1)
        next_display = next_duty.strftime("%d/%m")
        msg = f"Ngày mai ({tomorrow_display}) không có lịch trực.\nNgày trực tiếp theo: {next_display}."
        for cid in chat_ids:
            try:
                await context.bot.send_message(chat_id=int(cid), text=msg)
            except Exception as e:
                logger.error("Failed to send reminder: %s", e)
        return

    schedules = scheduler_service.get_schedules_by_date(tomorrow_str)
    if not schedules:
        return

    msg_parts = [f"Lịch trực ngày mai ({tomorrow_display}):"]
    for s in schedules:
        msg_parts.append(f"- {s.get('personnel_name', '?')}")

    msg = "\n".join(msg_parts)
    for cid in chat_ids:
        try:
            await context.bot.send_message(chat_id=int(cid), text=msg)
            logger.info("Reminder sent to %s", cid)
        except Exception as e:
            logger.error("Failed to send reminder to %s: %s", cid, e)


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

    job_queue.run_daily(daily_reminder, time=time(16, 0), days=tuple(range(7)), name="daily_reminder")
    job_queue.run_daily(weekly_approval_check, time=time(18, 0), days=(4,), name="weekly_approval_check")
    job_queue.run_repeating(retry_failed_notifications, interval=1800, first=10, name="retry_notifications")

    logger.info("Jobs setup complete")
