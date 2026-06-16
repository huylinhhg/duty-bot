from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def approval_keyboard(approval_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("✅ Duyệt", callback_data=f"appr_approve_{approval_id}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def delete_confirm_keyboard(item_type: str, item_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("Có", callback_data=f"del_yes_{item_type}_{item_id}"),
            InlineKeyboardButton("Không", callback_data=f"del_no_{item_type}_{item_id}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def yes_no_keyboard(callback_prefix: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("Có", callback_data=f"{callback_prefix}_yes"),
            InlineKeyboardButton("Không", callback_data=f"{callback_prefix}_no"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)
