import calendar
import logging
import re
from datetime import datetime, timedelta
from typing import Any

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

from duty_bot.config import BOT_TOKEN
from duty_bot.database.schema import create_tables
import duty_bot.database.repository as repo
from duty_bot.bot.conversations import (
    add_personnel_start,
    add_personnel_name,
    handle_continue,
    cancel as conv_cancel,
    ASK_NAME,
    ASK_CONTINUE,
)
from duty_bot.bot.keyboards import (
    approval_keyboard,
    delete_confirm_keyboard,
)
from duty_bot.services import personnel_service, scheduler_service, approval_service, report_service

logger = logging.getLogger(__name__)

WEEKDAYS = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]


def _display_date(db_date: str) -> str:
    if not db_date:
        return ""
    d = datetime.strptime(db_date, "%Y-%m-%d")
    wd = WEEKDAYS[d.weekday()]
    month = d.month
    if month == 1 or month == 12:
        return f"{d.strftime('%d/%m/%Y')} ({wd})"
    return f"{d.strftime('%d/%m')} ({wd})"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Bot quản lý lịch trực\n\n"
        "Các lệnh:\n"
        "/them - Thêm CBCS (hội thoại)\n"
        "/xoa ID1 [ID2 ...] - Xoá CBCS\n"
        "/xoa_all - Xoá tất cả CBCS (nhập lại)\n"
        "/ds - Danh sách CBCS\n"
        "/gen - Tạo mới hoặc xem lịch trực tháng hiện tại\n"
        "/xoa_lich - Xoá tất cả lịch trực\n"
        "/week - Xem lịch tuần này\n"
        "/today - Lịch hôm nay\n"

        "/approve ID - Duyệt lịch\n"
        "/bctuan - Báo cáo tuần này\n"
        "/bcthang - Báo cáo tháng này\n"
        "/stats - Thống kê\n"
    )


async def list_personnel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    personnel = repo.get_active_personnel()
    if not personnel:
        await update.message.reply_text("Chưa có CBCS nào.")
        return

    lines = ["Danh sách CBCS:"]
    for p in personnel:
        lines.append(f"  ID {p['id']}: {p['name']}")
    await update.message.reply_text("\n".join(lines))


async def clear_personnel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Bạn có chắc muốn xoá TẤT CẢ CBCS?", reply_markup=delete_confirm_keyboard("all_personnel", 0))


async def clear_schedules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    now = datetime.today()
    start = f"{now.year:04d}-{now.month:02d}-01"
    num_days = calendar.monthrange(now.year, now.month)[1]
    end = f"{now.year:04d}-{now.month:02d}-{num_days:02d}"
    schedules = scheduler_service.get_schedules_by_date_range(start, end)

    if not schedules:
        await update.message.reply_text("Hiện không có lịch trực nào.")
        return

    table = _format_schedule_table(schedules)
    await update.message.reply_text(
        f"{table}\n\nBạn có chắc muốn xoá TẤT CẢ lịch trực?",
        reply_markup=delete_confirm_keyboard("all_schedules", 0),
    )


async def xoa_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Dùng: /xoa ID1 [ID2 ID3 ...]")
        return
    removed = []
    not_found = []
    for arg in context.args:
        try:
            pid = int(arg)
        except ValueError:
            not_found.append(arg)
            continue
        p = personnel_service.validate_personnel_id(pid)
        if not p:
            not_found.append(str(pid))
            continue
        personnel_service.deactivate_personnel(pid)
        removed.append(p["name"])
    msg = ""
    if removed:
        msg += f"Đã xoá: {', '.join(removed)}."
    if not_found:
        msg += f"\nKhông tìm thấy: {', '.join(not_found)}."
    if not msg:
        msg = "Không có ai để xoá."
    await update.message.reply_text(msg)


def _format_schedule_table(schedules: list[dict[str, Any]]) -> str:
    if not schedules:
        return "Không có lịch trực."
    lines = ["```", f"{'STT':<4} | {'Ngày':<14} | {'Tên':<20}", "-" * 42]
    for i, s in enumerate(schedules, 1):
        d = datetime.strptime(s["date"], "%Y-%m-%d")
        date_label = _display_date(s["date"])
        name = s.get("personnel_name", "?")
        lines.append(f"{i:<4} | {date_label:<14} | {name:<20}")
    lines.append("```")
    return "\n".join(lines)


def _month_stats(year: int, month: int) -> str:
    num_days = calendar.monthrange(year, month)[1]
    start = f"{year:04d}-{month:02d}-01"
    end = f"{year:04d}-{month:02d}-{num_days:02d}"
    stats = repo.get_personnel_shift_count(start, end)
    if not stats:
        return ""
    lines = ["", "Thống kê:"]
    for s in stats:
        lines.append(f"  - {s['name']}: {s['shift_count']} ca")
    total = sum(s["shift_count"] for s in stats)
    lines.append(f"  Tổng: {total} ca")
    return "\n".join(lines)


async def generate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    now = datetime.today()
    year = now.year
    month = now.month
    if context.args:
        try:
            month = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Sai. Dùng: /gen MM (1-12) hoặc /gen")
            return
        if month < 1 or month > 12:
            await update.message.reply_text("Tháng phải từ 1-12.")
            return

    num_days = calendar.monthrange(year, month)[1]
    start = f"{year:04d}-{month:02d}-01"
    end = f"{year:04d}-{month:02d}-{num_days:02d}"
    existing = scheduler_service.get_schedules_by_date_range(start, end)

    if existing:
        table = _format_schedule_table(existing)
        stats = _month_stats(year, month)
        await update.message.reply_text(f"Bạn đang có lịch trực tháng {month}/{year}:\n\n{table}\n{stats}")
        return

    msg = await update.message.reply_text("Đang tạo lịch trực...")
    result = scheduler_service.generate_monthly_schedule(year, month)
    if "error" in result:
        await msg.edit_text(f"Lỗi: {result['error']}")
        return

    schedules = scheduler_service.get_schedules_by_date_range(start, end)
    table = _format_schedule_table(schedules)
    stats = _month_stats(year, month)
    await msg.edit_text(f"Đã tạo lịch trực tháng {month}/{year}.\n\n{table}\n{stats}")


async def week_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today = datetime.today()
    iso = today.isocalendar()
    year, week = iso[0], iso[1]

    schedules = scheduler_service.get_week_schedules(year, week)
    if not schedules:
        await update.message.reply_text(f"Tuần {week}/{year} không có lịch trực.")
        return

    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    lines = [
        f"Lịch trực tuần {week}/{year}",
        f"({monday.strftime('%d/%m')} - {sunday.strftime('%d/%m')}):",
        "",
    ]
    for s in schedules:
        d = _display_date(s["date"])
        name = s.get("personnel_name", "?")
        lines.append(f"  {d}: {name}")

    await update.message.reply_text("\n".join(lines))


async def today_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today_str = datetime.today().strftime("%Y-%m-%d")
    rows = scheduler_service.get_schedules_by_date(today_str)
    if not rows:
        await update.message.reply_text(f"Hôm nay ({_display_date(today_str)}) không có lịch trực.")
        return

    lines = [f"Lịch trực hôm nay ({_display_date(today_str)}):"]
    for r in rows:
        lines.append(f"  - {r.get('personnel_name', '?')}")
    await update.message.reply_text("\n".join(lines))


async def approve_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Dùng: /approve ID")
        return

    try:
        approval_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID phải là số.")
        return

    approval = approval_service.get_approval(approval_id)
    if not approval:
        await update.message.reply_text(f"Không tìm thấy phiếu duyệt #{approval_id}.")
        return

    success = approval_service.approve(approval_id, 0)
    if not success:
        await update.message.reply_text(f"Không thể duyệt phiếu #{approval_id}.")
        return

    await update.message.reply_text(
        f"Đã duyệt lịch #{approval_id}:\n"
        f"  {approval['week_start']} - {approval['week_end']}"
    )


async def bctuan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today = datetime.today()
    iso = today.isocalendar()
    text = report_service.weekly_report(iso[0], iso[1])
    await update.message.reply_text(text)


async def bcthang_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today = datetime.today()
    text = report_service.monthly_report(today.year, today.month)
    await update.message.reply_text(text)


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today = datetime.today()
    start = f"{today.year:04d}-{today.month:02d}-01"
    num_days = calendar.monthrange(today.year, today.month)[1]
    end = f"{today.year:04d}-{today.month:02d}-{num_days:02d}"

    stats = report_service.personnel_stats(start, end)
    if not stats["stats"]:
        await update.message.reply_text("Tháng này chưa có dữ liệu.")
        return

    lines = [
        f"Thống kê tháng {today.month}/{today.year}:",
        f"Tổng số ca: {stats['total']}",
        "",
    ]
    for s in stats["stats"]:
        lines.append(f"  - {s['name']}: {s['shift_count']} ca")

    if stats["most"]:
        lines.append(f"\nNhiều nhất: {stats['most']['name']} ({stats['most']['shift_count']} ca)")
    if stats["least"]:
        lines.append(f"Ít nhất: {stats['least']['name']} ({stats['least']['shift_count']} ca)")

    await update.message.reply_text("\n".join(lines))


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("appr_approve_"):
        approval_id = int(data.split("_")[2])
        approval = approval_service.get_approval(approval_id)
        if not approval:
            await query.edit_message_text("Không tìm thấy phiếu duyệt.")
            return
        success = approval_service.approve(approval_id, 0)
        if success:
            await query.edit_message_text(
                f"Đã duyệt lịch #{approval_id}:\n"
                f"  {approval['week_start']} - {approval['week_end']}"
            )
        else:
            await query.edit_message_text(f"Không thể duyệt #{approval_id}.")
    elif data.startswith("del_yes_all_personnel_"):
        count = repo.delete_all_personnel()
        await query.edit_message_text(f"Đã xoá {count} CBCS. Thêm lại bằng /them.")
    elif data.startswith("del_no_all_personnel_"):
        await query.edit_message_text("Đã huỷ.")
    elif data.startswith("del_yes_all_schedules_"):
        count = repo.delete_all_schedules()
        await query.edit_message_text(f"Đã xoá {count} lịch trực.")
    elif data.startswith("del_no_all_schedules_"):
        await query.edit_message_text("Đã huỷ.")
    else:
        await query.edit_message_text("Đã nhận yêu cầu.")


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
        entry_points=[CommandHandler("them", add_personnel_start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_personnel_name)],
            ASK_CONTINUE: [CallbackQueryHandler(handle_continue, pattern="^add_more_")],
        },
        fallbacks=[CommandHandler("cancel", conv_cancel)],
    )

    app.add_handler(add_personnel_conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ds", list_personnel))
    app.add_handler(CommandHandler("xoa", xoa_cmd))
    app.add_handler(CommandHandler("xoa_all", clear_personnel_cmd))
    app.add_handler(CommandHandler("xoa_lich", clear_schedules_cmd))
    app.add_handler(CommandHandler("gen", generate_cmd))
    app.add_handler(CommandHandler("week", week_cmd))
    app.add_handler(CommandHandler("today", today_cmd))
    app.add_handler(CommandHandler("approve", approve_cmd))
    app.add_handler(CommandHandler("bctuan", bctuan_cmd))
    app.add_handler(CommandHandler("bcthang", bcthang_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern="^(appr_|del_)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.add_error_handler(error_handler)

    return app
