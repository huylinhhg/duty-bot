import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import duty_bot.services.personnel_service as personnel_service
from duty_bot.models.entities import Personnel

logger = logging.getLogger(__name__)

ASK_NAME, ASK_POSITION = range(2)


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

    data = context.user_data["conv"]
    try:
        p = personnel_service.add_personnel(data["name"], data["position"])
        await update.message.reply_text(f"Đã thêm: {p.name}")
    except Exception as e:
        logger.error("Failed to add personnel: %s", e)
        await update.message.reply_text(f"Lỗi: {e}")
    context.user_data.pop("conv", None)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("conv", None)
    await update.message.reply_text("Đã huỷ.")
    return ConversationHandler.END
