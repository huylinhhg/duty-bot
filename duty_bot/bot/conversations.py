import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import duty_bot.services.personnel_service as personnel_service

logger = logging.getLogger(__name__)

ASK_NAME = 0


async def add_personnel_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["conv"] = {}
    await update.message.reply_text("Nhập tên CBCS:")
    return ASK_NAME


async def add_personnel_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Tên không được để trống. Nhập lại:")
        return ASK_NAME

    try:
        p = personnel_service.add_personnel(name, "")
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
