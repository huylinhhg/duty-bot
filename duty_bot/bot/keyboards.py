from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import Optional


def approval_keyboard(approval_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("✅ Duyệt", callback_data=f"appr_approve_{approval_id}"),
            InlineKeyboardButton("❌ Từ chối", callback_data=f"appr_reject_{approval_id}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def confirm_keyboard(schedule_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("✅ Đã nhận", callback_data=f"cf_recv_{schedule_id}"),
            InlineKeyboardButton("✅ Đã thực hiện", callback_data=f"cf_done_{schedule_id}"),
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


def schedule_selection_keyboard(schedules: list[dict], page: int = 0, page_size: int = 10) -> Optional[InlineKeyboardMarkup]:
    start = page * page_size
    end = start + page_size
    page_schedules = schedules[start:end]

    if not page_schedules:
        return None

    keyboard = []
    for s in page_schedules:
        date_display = s["date"]
        name = s.get("personnel_name", f"ID:{s['personnel_id']}")
        shift = s.get("shift", "")
        label = f"{date_display} - {name} ({shift})"
        keyboard.append([
            InlineKeyboardButton(label, callback_data=f"sel_sch_{s['id']}")
        ])

    nav = []
    total_pages = (len(schedules) + page_size - 1) // page_size
    if page > 0:
        nav.append(InlineKeyboardButton("⬅ Trước", callback_data=f"sch_page_{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Sau ➡", callback_data=f"sch_page_{page + 1}"))
    if nav:
        keyboard.append(nav)

    keyboard.append([InlineKeyboardButton("Huỷ", callback_data="sch_cancel")])
    return InlineKeyboardMarkup(keyboard)
