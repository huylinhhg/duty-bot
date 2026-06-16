import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
import lunardate

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise ValueError("Missing BOT_TOKEN in .env file")

CHAT_IDS = os.getenv("CHAT_IDS", "")
SHEET_ID = os.getenv("SHEET_ID", "")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh")
DATABASE_PATH = os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schedules.db"))

# Holiday configuration
# Fixed solar holidays: (month, day, duration_days)
# duration_days = số ngày được nghỉ (tính từ ngày đó trở đi)
FIXED_HOLIDAYS = [
    (1, 1, 1),      # Tết Dương lịch
    (4, 30, 2),     # 30/4 + 1/5 (nghỉ liền 2 ngày)
    (8, 19, 1),     # Ngày truyền thống CAND
    (9, 2, 2),      # Quốc khánh (nghỉ 2 ngày)
]

# Lunar holidays: (lunar_month, lunar_day, duration_days)
LUNAR_HOLIDAYS = [
    (3, 10, 1),     # Giỗ Tổ Hùng Vương
]

# Tết Nguyên đán: số ngày nghỉ trước và sau giao thừa
TET_BEFORE = 2   # nghỉ từ 29 Tết
TET_AFTER = 5    # đến hết mùng 5


def get_holiday_dates(year: int) -> set[str]:
    """Return set of date strings (YYYY-MM-DD) for all holidays in given year."""
    dates: set[str] = set()

    # Fixed holidays
    for month, day, duration in FIXED_HOLIDAYS:
        try:
            d = datetime(year, month, day)
            for i in range(duration):
                dates.add((d + timedelta(days=i)).strftime("%Y-%m-%d"))
        except ValueError:
            continue

    # Lunar holidays
    for l_month, l_day, duration in LUNAR_HOLIDAYS:
        try:
            d = lunardate.LunarDate(year, l_month, l_day).toSolarDate()
            for i in range(duration):
                dates.add((d + timedelta(days=i)).strftime("%Y-%m-%d"))
        except (ValueError, IndexError):
            continue

    # Tết Nguyên đán
    for ly in [year - 1, year]:
        try:
            new_year = lunardate.LunarDate(ly, 1, 1).toSolarDate()
            if new_year.year != year:
                continue
            # Before Tết (29, 30 Tết): thuộc lunar year trước đó (ly-1)
            prev_ly = ly - 1
            for day_offset in range(TET_BEFORE):
                try:
                    d = lunardate.LunarDate(prev_ly, 12, 29 + day_offset).toSolarDate()
                    if d.year == year:
                        dates.add(d.strftime("%Y-%m-%d"))
                except (ValueError, IndexError):
                    # Tháng 12 chỉ có 29 ngày, skip day 30
                    if day_offset == 0:
                        pass
            # After Tết: từ mùng 1 đến mùng 5 (thuộc lunar year ly)
            for day in range(1, TET_AFTER + 1):
                try:
                    d = lunardate.LunarDate(ly, 1, day).toSolarDate()
                    dates.add(d.strftime("%Y-%m-%d"))
                except (ValueError, IndexError):
                    continue
        except (ValueError, IndexError):
            continue

    return dates
