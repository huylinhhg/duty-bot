import logging

from duty_bot.config import BOT_TOKEN
from duty_bot.database.connection import get_db
from duty_bot.database.schema import create_tables
from duty_bot.bot.handlers import setup_handlers
from duty_bot.scheduler.jobs import setup_jobs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_MEMBERS = ['Tuấn', 'Lan', 'Mai', 'Hùng', 'Nam', 'Hà', 'Sơn', 'Linh', 'Phúc', 'Dũng']


def seed_members():
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) as cnt FROM personnel").fetchone()["cnt"]
        if count == 0:
            for i, name in enumerate(DEFAULT_MEMBERS, 1):
                conn.execute(
                    "INSERT INTO personnel (name, position, group_name) VALUES (?, ?, ?)",
                    (name, 'Nhân viên', 'Tổ 1'),
                )
            logger.info("Seeded %d default members", len(DEFAULT_MEMBERS))


def main() -> None:
    create_tables()
    seed_members()
    logger.info("Database initialized")

    app = setup_handlers()
    setup_jobs(app)

    logger.info("Bot started, polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
