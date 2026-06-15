import logging
from datetime import datetime, time, timedelta

import pytz
from telegram.ext import Application, ContextTypes

from duty_bot.config import CHAT_IDS, TIMEZONE
from duty_bot.services import scheduler_service, report_service, notification_service
import duty_bot.database.repository as repo

logger = logging.getLogger(__name__)


async def daily_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    today_str = datetime.today().strftime("%Y-%m-%d")
    schedules = scheduler_service.get_schedules_by_date(today_str)
    if not schedules:
        return

    chat_ids = [c.strip() for c in CHAT_IDS.split(",") if c.strip()]
    if not chat_ids:
        return

    msg_parts = [f"Lịch trực hôm nay ({today_str}):"]
    for s in schedules:
        msg_parts.append(f"- {s.get('personnel_name', '?')}")
    msg = "\n".join(msg_parts)

    for cid in chat_ids:
        try:
            await context.bot.send_message(chat_id=int(cid), text=msg)
            logger.info("Daily reminder sent to %s", cid)
        except Exception as e:
            logger.error("Failed to send daily reminder to %s: %s", cid, e)


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


async def confirmation_check(context: ContextTypes.DEFAULT_TYPE) -> None:
    today_str = datetime.today().strftime("%Y-%m-%d")
    schedules = scheduler_service.get_schedules_by_date(today_str)
    if not schedules:
        return

    chat_ids = [c.strip() for c in CHAT_IDS.split(",") if c.strip()]
    for s in schedules:
        if s["status"] != "deployed":
            chat_id = s.get("chat_id") or (chat_ids[0] if chat_ids else None)
            if not chat_id:
                continue
            msg = (
                f"🔔 Nhắc nhở: Bạn chưa xác nhận trực hôm nay ({today_str}).\n"
                f"Dùng /confirm {s['id']} để xác nhận."
            )
            try:
                await context.bot.send_message(chat_id=int(chat_id), text=msg)
                logger.info("Confirmation check sent for schedule id=%d", s["id"])
            except Exception as e:
                logger.error("Failed to send confirmation check: %s", e)


async def tomorrow_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    tomorrow = (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    schedules = scheduler_service.get_schedules_by_date(tomorrow)
    if not schedules:
        return

    chat_ids = [c.strip() for c in CHAT_IDS.split(",") if c.strip()]
    if not chat_ids:
        return

    msg_parts = [f"Nhắc lịch trực ngày mai ({tomorrow}):"]
    for s in schedules:
        msg_parts.append(f"- {s.get('personnel_name', '?')}")
    msg = "\n".join(msg_parts)

    for cid in chat_ids:
        try:
            await context.bot.send_message(chat_id=int(cid), text=msg)
        except Exception as e:
            logger.error("Failed to send tomorrow reminder to %s: %s", cid, e)


def setup_jobs(app: Application) -> None:
    tz = pytz.timezone(TIMEZONE)

    job_queue = app.job_queue
    if not job_queue:
        logger.warning("No job queue available")
        return

    job_queue.run_daily(daily_reminder, time=time(7, 0), days=tuple(range(7)), name="daily_reminder")
    job_queue.run_daily(tomorrow_reminder, time=time(18, 0), days=tuple(range(7)), name="tomorrow_reminder")
    job_queue.run_daily(weekly_approval_check, time=time(18, 0), days=(4,), name="weekly_approval_check")
    job_queue.run_repeating(retry_failed_notifications, interval=1800, first=10, name="retry_notifications")
    job_queue.run_daily(confirmation_check, time=time(20, 0), days=tuple(range(7)), name="confirmation_check")

    logger.info("Jobs setup complete")
