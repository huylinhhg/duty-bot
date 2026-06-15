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


def main() -> None:
    create_tables()
    logger.info("Database initialized")

    app = setup_handlers()
    setup_jobs(app)

    logger.info("Bot started, polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
