import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise ValueError("Missing BOT_TOKEN in .env file")

CHAT_IDS = os.getenv("CHAT_IDS", "")
SHEET_ID = os.getenv("SHEET_ID", "")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh")
DATABASE_PATH = os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schedules.db"))
