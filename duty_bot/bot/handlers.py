import calendar
import logging
import re
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from duty_bot.config import BOT_TOKEN, CHAT_IDS, SHEET_ID, TIMEZONE
from duty_bot.database.schema import create_tables
import duty_bot.database.repository as repo
from duty_bot.bot.conversations import (
    add_personnel_start,
    add_personnel_name,
    add_personnel_position,
    add_personnel_group,
    confirm_duty_start,
    cancel as conv_cancel,
    ASK_NAME,
    ASK_POSITION,
    ASK_GROUP,
    CONFIRM_SELECT,
)
from duty_bot.bot.keyboards import (
    approval_keyboard,
    confirm_keyboard,
    delete_confirm_keyboard,
    schedule_selection_keyboard,
)
from duty_bot.services import personnel_service, scheduler_service, approval_service, notification_service, report_service
from duty_bot.services.sheet_service import export_to_sheet, import_from_sheet as sheet_import

logger = logging.getLogger(__name__)

SHIFT_LABELS = {"": "", "": "", "": ""}
WEEKDAYS = ["", "", "", "", "", "", ""]


def _display_date(db_date: str) -> str:
    if not db_date:
        return ""
    d = datetime.strptime(db_date, "")
    wd = WEEKDAYS[d.weekday()]
    return "f"


def _shift_label(s: str) -> str:
    return SHIFT_LABELS.get(s, s)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        ""
        ""
        ""
        ""
        ""
        ""
        ""
        ""
        ""
        ""
        ""
        ""
        ""
        ""
        ""
        ""
    )


async def list_personnel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    personnel = personnel_service.get_personnel()
    if not personnel:
        await update.message.reply_text("")
        return

    lines = [""]
    for p in personnel:
        active = "" if p[""] else ""
        lines.append(
            "f"
            "f"
        )
    await update.message.reply_text("".join(lines))


async def exclude_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            ""
            ""
        )
        return

    parts = context.args[0].split("")
    if len(parts) < 3:
        await update.message.reply_text("")
        return

    try:
        personnel_id = int(parts[0])
        start_date = parts[1]
        end_date = parts[2]
        reason = "".join(parts[3:]) if len(parts) > 3 else ""
    except ValueError:
        await update.message.reply_text("")
        return

    p = personnel_service.validate_personnel_id(personnel_id)
    if not p:
        await update.message.reply_text("f")
        return

    try:
        personnel_service.add_exclusion(personnel_id, start_date, end_date, reason)
        await update.message.reply_text(
            "f"
            "f"
            "f"
        )
    except Exception as e:
        logger.error("", e)
        await update.message.reply_text("f")


async def generate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    now = datetime.today()
    year = now.year
    month = now.month
    if context.args:
        match = re.match(r"", context.args[0])
        if not match:
            await update.message.reply_text("")
            return
        month = int(match.group(1))
        year = int(match.group(2))
        if month < 1 or month > 12:
            await update.message.reply_text("")
            return

    msg = await update.message.reply_text("")
    result = scheduler_service.generate_monthly_schedule(year, month)
    if "" in result:
        await msg.edit_text("f")
        return
    await msg.edit_text("f")


async def week_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today = datetime.today()
    iso = today.isocalendar()
    year, week = iso[0], iso[1]

    schedules = scheduler_service.get_week_schedules(year, week)
    if not schedules:
        await update.message.reply_text("f")
        return

    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    lines = [
        "f",
        "f",
        "",
    ]
    for s in schedules:
        d = _display_date(s[""])
        shift_lbl = _shift_label(s[""])
        name = s.get("", "")
        status_icon = ""
        if s[""] == "":
            status_icon = ""
        elif s[""] == "":
            status_icon = ""
        lines.append("f")

    await update.message.reply_text("".join(lines))


async def today_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today_str = datetime.today().strftime("")
    rows = scheduler_service.get_schedules_by_date(today_str)
    if not rows:
        await update.message.reply_text("f")
        return

    lines = ["f"]
    for r in rows:
        shift_lbl = _shift_label(r[""])
        name = r.get("", "")
        lines.append("f")
    await update.message.reply_text("".join(lines))


async def submit_approval_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today = datetime.today()
    next_monday = today + timedelta(days=(7 - today.weekday()))
    next_sunday = next_monday + timedelta(days=6)
    week_start = next_monday.strftime("")
    week_end = next_sunday.strftime("")

    approval = approval_service.submit_for_approval(week_start, week_end)
    if not approval:
        await update.message.reply_text("f")
        return

    await update.message.reply_text(
        "f"
        "f"
        "f",
        reply_markup=approval_keyboard(approval.id),
    )


async def approve_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("")
        return

    try:
        approval_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("")
        return

    comment = "".join(context.args[1:]) if len(context.args) > 1 else ""

    approval = approval_service.get_approval(approval_id)
    if not approval:
        await update.message.reply_text("f")
        return

    user = update.effective_user
    approver_name = user.full_name or str(user.id)

    success = approval_service.approve(approval_id, 0)
    if not success:
        await update.message.reply_text("f")
        return

    await update.message.reply_text(
        "f"
        "f"
        "f"
    )


async def reject_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("")
        return

    try:
        approval_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("")
        return

    comment = "".join(context.args[1:]) if len(context.args) > 1 else ""

    approval = approval_service.get_approval(approval_id)
    if not approval:
        await update.message.reply_text("f")
        return

    success = approval_service.reject(approval_id, 0, comment)
    if not success:
        await update.message.reply_text("f")
        return

    await update.message.reply_text(
        "f"
        "f"
        "f"
    )


async def confirm_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        try:
            schedule_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("")
            return
        schedule = repo.get_schedule_by_id(schedule_id)
        if not schedule:
            await update.message.reply_text("f")
            return
        await update.message.reply_text(
            "f"
            "f"
            "f"
            "f",
            reply_markup=confirm_keyboard(schedule[""]),
        )
    else:
        today_str = datetime.today().strftime("")
        schedules = scheduler_service.get_schedules_by_date(today_str)
        if not schedules:
            await update.message.reply_text("")
            return
        if len(schedules) == 1:
            s = schedules[0]
            await update.message.reply_text(
                "f"
                "f"
                "f",
                reply_markup=confirm_keyboard(s[""]),
            )
        else:
            msg = ""
            for s in schedules:
                msg += "f"
            msg += ""
            await update.message.reply_text(msg)


async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("")
        return

    today = datetime.today()
    report_type = context.args[0].lower()

    if report_type == "":
        iso = today.isocalendar()
        text = report_service.weekly_report(iso[0], iso[1])
    elif report_type == "":
        text = report_service.monthly_report(today.year, today.month)
    else:
        await update.message.reply_text("")
        return

    await update.message.reply_text(text)


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today = datetime.today()
    start = "f"
    num_days = calendar.monthrange(today.year, today.month)[1]
    end = "f"

    stats = report_service.personnel_stats(start, end)
    if not stats[""]:
        await update.message.reply_text("")
        return

    lines = [
        "f",
        "f",
        "",
    ]
    for s in stats[""]:
        lines.append("f")

    if stats[""]:
        lines.append("f")
    if stats[""]:
        lines.append("f")

    await update.message.reply_text("".join(lines))


async def sync_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not SHEET_ID:
        await update.message.reply_text("")
        return
    if not context.args or context.args[0] not in ("", ""):
        await update.message.reply_text("")
        return

    direction = context.args[0]
    if direction == "":
        success = export_to_sheet(SHEET_ID)
        if success:
            await update.message.reply_text("")
        else:
            await update.message.reply_text("")
    else:
        imported = sheet_import(SHEET_ID)
        if not imported:
            await update.message.reply_text("")
            return
        count = 0
        for r in imported:
            try:
                repo.add_schedule(
                    date=r[""],
                    shift=r[""],
                    personnel_id=r[""],
                    group_name=r.get("", ""),
                    status=r.get("", ""),
                    source="",
                )
                count += 1
            except Exception as e:
                logger.error("", e)
        await update.message.reply_text("f")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith(""):
        approval_id = int(data.split("")[2])
        approval = approval_service.get_approval(approval_id)
        if not approval:
            await query.edit_message_text("")
            return
        success = approval_service.approve(approval_id, 0)
        if success:
            await query.edit_message_text(
                "f"
                "f"
            )
        else:
            await query.edit_message_text("f")
    elif data.startswith(""):
        approval_id = int(data.split("")[2])
        approval = approval_service.get_approval(approval_id)
        if not approval:
            await query.edit_message_text("")
            return
        success = approval_service.reject(approval_id, 0, "")
        if success:
            await query.edit_message_text(
                "f"
                "f"
            )
        else:
            await query.edit_message_text("f")
    elif data.startswith(""):
        schedule_id = int(data.split("")[2])
        await query.edit_message_text("f")
    elif data.startswith(""):
        schedule_id = int(data.split("")[2])
        repo.update_schedule(schedule_id, status="")
        repo.add_audit_log("", "", schedule_id, "")
        await query.edit_message_text("f")
    elif data == "":
        await query.edit_message_text("")
    elif data.startswith(""):
        page = int(data.split("")[2])
        try:
            schedules = context.user_data.get("", [])
            kb = schedule_selection_keyboard(schedules, page)
            if kb:
                await query.edit_message_text(
                    "f",
                    reply_markup=kb,
                )
        except Exception as e:
            logger.error("", e)
    else:
        await query.edit_message_text("")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Dùng /start để xem hướng dẫn.")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling update: %s", context.error)
    if update and update.effective_message:
        await update.effective_message.reply_text(f"Lỗi: {context.error}")


def setup_handlers() -> Application:
    create_tables()

    app = Application.builder().token(BOT_TOKEN).build()

    add_personnel_conv = ConversationHandler(
        entry_points=[CommandHandler("add_personnel", add_personnel_start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_personnel_name)],
            ASK_POSITION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_personnel_position)],
            ASK_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_personnel_group)],
        },
        fallbacks=[CommandHandler("cancel", conv_cancel)],
    )

    app.add_handler(add_personnel_conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list_personnel", list_personnel))
    app.add_handler(CommandHandler("exclude", exclude_cmd))
    app.add_handler(CommandHandler("gen", generate_cmd))
    app.add_handler(CommandHandler("week", week_cmd))
    app.add_handler(CommandHandler("today", today_cmd))
    app.add_handler(CommandHandler("submit_approval", submit_approval_cmd))
    app.add_handler(CommandHandler("approve", approve_cmd))
    app.add_handler(CommandHandler("reject", reject_cmd))
    app.add_handler(CommandHandler("confirm", confirm_cmd))
    app.add_handler(CommandHandler("report", report_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("sync", sync_cmd))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern="^(appr_|cf_|sch_|del_)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.add_error_handler(error_handler)

    return app
