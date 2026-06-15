import logging
from typing import Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

import duty_bot.services.personnel_service as personnel_service
from duty_bot.services import scheduler_service
from duty_bot.bot.keyboards import confirm_keyboard

logger = logging.getLogger(__name__)

ASK_NAME, ASK_POSITION, ASK_GROUP = range(3, 6)
CONFIRM_SELECT = range(6, 7)


async def add_personnel_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["conv"] = {}
    await update.message.reply_text("Nhập tên CBCS:")
    return ASK_NAME


async def add_personnel_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Tên không được để trống. Nhập lại:")
        return ASK_NAME
    context.user_data["conv"]["name"] = name
    await update.message.reply_text("Nhập chức vụ (hoặc /skip để bỏ qua):")
    return ASK_POSITION


async def add_personnel_position(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == "/skip":
        context.user_data["conv"]["position"] = ""
    else:
        context.user_data["conv"]["position"] = text
    await update.message.reply_text("Nhập tổ trực (hoặc /skip để bỏ qua):")
    return ASK_GROUP


async def add_personnel_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == "/skip":
        context.user_data["conv"]["group_name"] = ""
    else:
        context.user_data["conv"]["group_name"] = text

    data = context.user_data["conv"]
    try:
        p = personnel_service.add_personnel(data["name"], data["position"], data["group_name"])
        await update.message.reply_text(
            f"Đã thêm CBCS:\n"
            f"  Tên: {p.name}\n"
            f"  Chức vụ: {p.position or '(trống)'}\n"
            f"  Tổ: {p.group_name or '(trống)'}"
        )
    except Exception as e:
        logger.error("Failed to add personnel: %s", e)
        await update.message.reply_text(f"Lỗi: {e}")
    context.user_data.pop("conv", None)
    return ConversationHandler.END


async def confirm_duty_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    today = scheduler_service.get_schedules_by_date("")
    import datetime
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    schedules = scheduler_service.get_schedules_by_date(today_str)

    if not schedules:
        await update.message.reply_text("Hôm nay bạn không có lịch trực.")
        return ConversationHandler.END

    if len(schedules) == 1:
        context.user_data["confirm_schedule"] = schedules[0]
        s = schedules[0]
        await update.message.reply_text(
            f"Xác nhận trực:\n"
            f"  Ngày: {s['date']}\n"
            f"  Ca: {s['shift']}\n"
            f"  Người: {s.get('personnel_name', '?')}",
            reply_markup=confirm_keyboard(s["id"]),
        )
        return CONFIRM_SELECT
    else:
        msg = "Hôm nay có nhiều lịch trực. Chọn lịch của bạn:\n"
        for s in schedules:
            msg += f"  ID {s['id']}: {s.get('personnel_name', '?')} - ca {s['shift']}\n"
        msg += "\nGõ /confirm ID để chọn."
        await update.message.reply_text(msg)
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("conv", None)
    await update.message.reply_text("Đã huỷ.")
    return ConversationHandler.END
