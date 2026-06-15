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

SHIFT_LABELS = {"sang": "Sáng", "chieu": "Chiều", "toi": "Tối"}
WEEKDAYS = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]


def _display_date(db_date: str) -> str:
    if not db_date:
        return ""
    d = datetime.strptime(db_date, "%Y-%m-%d")
    wd = WEEKDAYS[d.weekday()]
    return f"{d.strftime('%d/%m/%Y')} ({wd})"


def _shift_label(s: str) -> str:
    return SHIFT_LABELS.get(s, s)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Bot quản lý lịch trực\n\n"
        "Các lệnh:\n"
        "/add_personnel - Thêm CBCS (hội thoại)\n"
        "/remove_personnel ID - Xoá CBCS\n"
        "/clear_personnel - Xoá tất cả CBCS (nhập lại)\n"
        "/list_personnel - Danh sách CBCS\n"
        "/exclude ID_NgàyBD_NgàyKT_LýDo - Khai báo nghỉ\n"
        "/gen MM/YYYY - Sinh lịch tháng\n"
        "/week - Xem lịch tuần này\n"
        "/today - Lịch hôm nay\n"
        "/submit_approval - Gửi duyệt tuần tiếp\n"
        "/approve ID - Duyệt lịch\n"
        "/reject ID lý_do - Từ chối\n"
        "/confirm - Xác nhận trực\n"
        "/report week|month - Báo cáo\n"
        "/stats - Thống kê\n"
        "/sync export|import - Đồng bộ Google Sheet\n\n"
        "Định dạng ngày: YYYY-MM-DD"
    )


async def list_personnel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    personnel = personnel_service.get_personnel()
    if not personnel:
        await update.message.reply_text("Chưa có CBCS nào.")
        return

    lines = ["Danh sách CBCS:"]
    for p in personnel:
        active = "✅" if p["is_active"] else "❌"
        name_display = p["name"]
        if not p["is_active"]:
            name_display += " (đã xoá)"
        lines.append(
            f"  ID {p['id']}: {name_display} - {p['position'] or 'NV'} "
            f"(Tổ: {p['group_name'] or 'N/A'}) {active}"
        )
    await update.message.reply_text("\n".join(lines))


async def clear_personnel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Bạn có chắc muốn xoá TẤT CẢ CBCS?", reply_markup=delete_confirm_keyboard("all_personnel", 0))


async def remove_personnel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Dùng: /remove_personnel ID")
        return
    try:
        personnel_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID phải là số.")
        return
    p = personnel_service.validate_personnel_id(personnel_id)
    if not p:
        await update.message.reply_text(f"Không tìm thấy CBCS ID {personnel_id}.")
        return
    personnel_service.deactivate_personnel(personnel_id)
    await update.message.reply_text(f"Đã xoá {p['name']} khỏi danh sách.")


async def exclude_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Sai cú pháp. Dùng: /exclude ID_NgàyBD_NgàyKT_LýDo\n"
            "VD: /exclude 1_2025-03-10_2025-03-12_Nghỉ phép"
        )
        return

    parts = context.args[0].split("_")
    if len(parts) < 3:
        await update.message.reply_text("Cần ít nhất: ID_NgàyBD_NgàyKT")
        return

    try:
        personnel_id = int(parts[0])
        start_date = parts[1]
        end_date = parts[2]
        reason = "_".join(parts[3:]) if len(parts) > 3 else ""
    except ValueError:
        await update.message.reply_text("ID phải là số.")
        return

    p = personnel_service.validate_personnel_id(personnel_id)
    if not p:
        await update.message.reply_text(f"Không tìm thấy CBCS ID {personnel_id}.")
        return

    try:
        personnel_service.add_exclusion(personnel_id, start_date, end_date, reason)
        await update.message.reply_text(
            f"Đã thêm ngày nghỉ cho {p['name']}:\n"
            f"  {start_date} -> {end_date}\n"
            f"  Lý do: {reason or '(không có)'}"
        )
    except Exception as e:
        logger.error("Failed to add exclusion: %s", e)
        await update.message.reply_text(f"Lỗi: {e}")


async def generate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    now = datetime.today()
    year = now.year
    month = now.month
    if context.args:
        match = re.match(r"(\d{1,2})/(\d{4})", context.args[0])
        if not match:
            await update.message.reply_text("Sai. Dùng: /gen MM/YYYY")
            return
        month = int(match.group(1))
        year = int(match.group(2))
        if month < 1 or month > 12:
            await update.message.reply_text("Tháng phải từ 1-12.")
            return

    msg = await update.message.reply_text("Đang tạo lịch trực...")
    result = scheduler_service.generate_monthly_schedule(year, month)
    if "error" in result:
        await msg.edit_text(f"Lỗi: {result['error']}")
        return
    await msg.edit_text(f"Đã tạo {result['total']} lịch trực tháng {month}/{year}.")


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
        f"({monday.strftime('%d/%m/%Y')} - {sunday.strftime('%d/%m/%Y')}):",
        "",
    ]
    for s in schedules:
        d = _display_date(s["date"])
        shift_lbl = _shift_label(s["shift"])
        name = s.get("personnel_name", "?")
        status_icon = ""
        if s["status"] == "approved":
            status_icon = " ✅"
        elif s["status"] == "pending_approval":
            status_icon = " ⏳"
        lines.append(f"  {d}: {name} (ca {shift_lbl}){status_icon}")

    await update.message.reply_text("\n".join(lines))


async def today_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today_str = datetime.today().strftime("%Y-%m-%d")
    rows = scheduler_service.get_schedules_by_date(today_str)
    if not rows:
        await update.message.reply_text(f"Hôm nay ({_display_date(today_str)}) không có lịch trực.")
        return

    lines = [f"Lịch trực hôm nay ({_display_date(today_str)}):"]
    for r in rows:
        shift_lbl = _shift_label(r["shift"])
        name = r.get("personnel_name", "?")
        lines.append(f"  - {name} (ca {shift_lbl})")
    await update.message.reply_text("\n".join(lines))


async def submit_approval_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today = datetime.today()
    next_monday = today + timedelta(days=(7 - today.weekday()))
    next_sunday = next_monday + timedelta(days=6)
    week_start = next_monday.strftime("%Y-%m-%d")
    week_end = next_sunday.strftime("%Y-%m-%d")

    approval = approval_service.submit_for_approval(week_start, week_end)
    if not approval:
        await update.message.reply_text(f"Tuần {week_start} - {week_end} đã được gửi duyệt trước đó.")
        return

    await update.message.reply_text(
        f"Đã gửi duyệt lịch tuần:\n"
        f"  {_display_date(week_start)} - {_display_date(week_end)}\n"
        f"Mã duyệt: #{approval.id}",
        reply_markup=approval_keyboard(approval.id),
    )


async def approve_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Dùng: /approve ID [comment]")
        return

    try:
        approval_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID phải là số.")
        return

    comment = " ".join(context.args[1:]) if len(context.args) > 1 else ""

    approval = approval_service.get_approval(approval_id)
    if not approval:
        await update.message.reply_text(f"Không tìm thấy phiếu duyệt #{approval_id}.")
        return

    user = update.effective_user
    approver_name = user.full_name or str(user.id)

    success = approval_service.approve(approval_id, 0)
    if not success:
        await update.message.reply_text(f"Không thể duyệt phiếu #{approval_id}.")
        return

    await update.message.reply_text(
        f"Đã duyệt lịch #{approval_id}:\n"
        f"  {approval['week_start']} - {approval['week_end']}\n"
        f"  Người duyệt: {approver_name}"
    )


async def reject_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Dùng: /reject ID [lý_do]")
        return

    try:
        approval_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID phải là số.")
        return

    comment = " ".join(context.args[1:]) if len(context.args) > 1 else ""

    approval = approval_service.get_approval(approval_id)
    if not approval:
        await update.message.reply_text(f"Không tìm thấy phiếu duyệt #{approval_id}.")
        return

    success = approval_service.reject(approval_id, 0, comment)
    if not success:
        await update.message.reply_text(f"Không thể từ chối phiếu #{approval_id}.")
        return

    await update.message.reply_text(
        f"Đã từ chối lịch #{approval_id}:\n"
        f"  {approval['week_start']} - {approval['week_end']}\n"
        f"  Lý do: {comment or '(không có)'}"
    )


async def confirm_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        try:
            schedule_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("ID phải là số.")
            return
        schedule = repo.get_schedule_by_id(schedule_id)
        if not schedule:
            await update.message.reply_text(f"Không tìm thấy lịch #{schedule_id}.")
            return
        await update.message.reply_text(
            f"Xác nhận trực:\n"
            f"  Ngày: {schedule['date']}\n"
            f"  Ca: {schedule['shift']}\n"
            f"  Người: {schedule.get('personnel_name', '?')}",
            reply_markup=confirm_keyboard(schedule["id"]),
        )
    else:
        today_str = datetime.today().strftime("%Y-%m-%d")
        schedules = scheduler_service.get_schedules_by_date(today_str)
        if not schedules:
            await update.message.reply_text("Hôm nay không có lịch trực nào để xác nhận.")
            return
        if len(schedules) == 1:
            s = schedules[0]
            await update.message.reply_text(
                f"Xác nhận trực:\n"
                f"  Ngày: {s['date']} - Ca: {s['shift']}\n"
                f"  Người: {s.get('personnel_name', '?')}",
                reply_markup=confirm_keyboard(s["id"]),
            )
        else:
            msg = "Hôm nay có nhiều lịch trực. Chọn ID:\n"
            for s in schedules:
                msg += f"  #{s['id']}: {s.get('personnel_name', '?')} - ca {s['shift']}\n"
            msg += "\nVD: /confirm ID"
            await update.message.reply_text(msg)


async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Dùng: /report week hoặc /report month")
        return

    today = datetime.today()
    report_type = context.args[0].lower()

    if report_type == "week":
        iso = today.isocalendar()
        text = report_service.weekly_report(iso[0], iso[1])
    elif report_type == "month":
        text = report_service.monthly_report(today.year, today.month)
    else:
        await update.message.reply_text("Chọn: week hoặc month")
        return

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


async def sync_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not SHEET_ID:
        await update.message.reply_text("Chưa cấu hình SHEET_ID trong .env")
        return
    if not context.args or context.args[0] not in ("export", "import"):
        await update.message.reply_text("Dùng: /sync export hoặc /sync import")
        return

    direction = context.args[0]
    if direction == "export":
        success = export_to_sheet(SHEET_ID)
        if success:
            await update.message.reply_text("Đã xuất lên Google Sheet.")
        else:
            await update.message.reply_text("Xuất thất bại.")
    else:
        imported = sheet_import(SHEET_ID)
        if not imported:
            await update.message.reply_text("Không có dữ liệu nhập từ sheet.")
            return
        count = 0
        for r in imported:
            try:
                repo.add_schedule(
                    date=r["date"],
                    shift=r["shift"],
                    personnel_id=r["personnel_id"],
                    group_name=r.get("group_name", ""),
                    status=r.get("status", "draft"),
                    source="imported",
                )
                count += 1
            except Exception as e:
                logger.error("Failed to import schedule: %s", e)
        await update.message.reply_text(f"Đã nhập {count}/{len(imported)} lịch trực.")


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
    elif data.startswith("appr_reject_"):
        approval_id = int(data.split("_")[2])
        approval = approval_service.get_approval(approval_id)
        if not approval:
            await query.edit_message_text("Không tìm thấy phiếu duyệt.")
            return
        success = approval_service.reject(approval_id, 0, "Từ chối qua Telegram")
        if success:
            await query.edit_message_text(
                f"Đã từ chối lịch #{approval_id}:\n"
                f"  {approval['week_start']} - {approval['week_end']}"
            )
        else:
            await query.edit_message_text(f"Không thể từ chối #{approval_id}.")
    elif data.startswith("cf_recv_"):
        schedule_id = int(data.split("_")[2])
        await query.edit_message_text(f"Đã xác nhận tiếp nhận lịch #{schedule_id}.")
    elif data.startswith("cf_done_"):
        schedule_id = int(data.split("_")[2])
        repo.update_schedule(schedule_id, status="deployed")
        repo.add_audit_log("confirm_duty", "schedule", schedule_id, "{}")
        await query.edit_message_text(f"Đã xác nhận hoàn thành lịch #{schedule_id}.")
    elif data.startswith("del_yes_all_personnel_"):
        count = repo.delete_all_personnel()
        await query.edit_message_text(f"Đã xoá {count} CBCS. Thêm lại bằng /add_personnel.")
    elif data.startswith("del_no_all_personnel_"):
        await query.edit_message_text("Đã huỷ.")
    elif data == "sch_cancel":
        await query.edit_message_text("Đã huỷ.")
    elif data.startswith("sch_page_"):
        page = int(data.split("_")[2])
        try:
            schedules = context.user_data.get("sch_list", [])
            kb = schedule_selection_keyboard(schedules, page)
            if kb:
                await query.edit_message_text(
                    f"Chọn lịch (trang {page + 1}/{(len(schedules) + 9) // 10}):",
                    reply_markup=kb,
                )
        except Exception as e:
            logger.error("Page error: %s", e)
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
    app.add_handler(CommandHandler("remove_personnel", remove_personnel_cmd))
    app.add_handler(CommandHandler("clear_personnel", clear_personnel_cmd))
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
