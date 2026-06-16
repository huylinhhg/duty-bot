import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import duty_bot.services.personnel_service as personnel_service

logger = logging.getLogger(__name__)

ASK_NAME = 0


async def add_personnel_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["conv"] = {}
    await update.message.reply_text("Nhập tên CBCS (mỗi dòng một tên):")
    return ASK_NAME


async def add_personnel_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Không được để trống. Nhập lại:")
        return ASK_NAME

    names = [line.strip() for line in text.split("\n") if line.strip()]
    added = []
    for name in names:
        try:
            p = personnel_service.add_personnel(name, "")
            added.append(p.name)
        except Exception as e:
            logger.error("Failed to add personnel %s: %s", name, e)
            added.append(f"{name} (lỗi: {e})")

    if added:
        await update.message.reply_text(f"Đã thêm:\n" + "\n".join(f"  - {n}" for n in added))
    context.user_data.pop("conv", None)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("conv", None)
    await update.message.reply_text("Đã huỷ.")
    return ConversationHandler.END
