import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import duty_bot.services.personnel_service as personnel_service
from duty_bot.bot.keyboards import yes_no_keyboard

logger = logging.getLogger(__name__)

ASK_NAME, ASK_CONTINUE = range(2)


async def add_personnel_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["conv"] = {"added": []}
    await update.message.reply_text("Nhập tên CBCS (mỗi dòng một tên):")
    return ASK_NAME


async def add_personnel_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Không được để trống. Nhập lại:")
        return ASK_NAME

    names = [line.strip() for line in text.split("\n") if line.strip()]
    added = context.user_data["conv"]["added"]
    for name in names:
        try:
            p = personnel_service.add_personnel(name, "")
            added.append(p.name)
        except Exception as e:
            logger.error("Failed to add personnel %s: %s", name, e)
            added.append(f"{name} (lỗi)")

    await update.message.reply_text(
        f"Đã thêm {len(names)} người.\nCòn ai nữa không?",
        reply_markup=yes_no_keyboard("add_more"),
    )
    return ASK_CONTINUE


async def handle_continue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "add_more_yes":
        await query.edit_message_text("Nhập tên CBCS (mỗi dòng một tên):")
        return ASK_NAME
    else:
        added = context.user_data["conv"]["added"]
        if added:
            msg = "Danh sách CBCS của bạn:\n" + "\n".join(f"  - {n}" for n in added)
        else:
            msg = "Chưa thêm ai."
        await query.edit_message_text(msg)
        context.user_data.pop("conv", None)
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("conv", None)
    await update.message.reply_text("Đã huỷ.")
    return ConversationHandler.END
