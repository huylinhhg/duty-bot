import asyncio
import hashlib
import logging
import time
from datetime import date
from typing import Optional

import duty_bot.database.repository as repo

logger = logging.getLogger(__name__)


def _make_idempotency_key(chat_id: str, message: str, notification_type: str) -> str:
    raw = f"{chat_id}|{message}|{notification_type}|{date.today().isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:40]


def send_notification(
    chat_id: str,
    message: str,
    notification_type: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
) -> Optional[str]:
    idempotency_key = _make_idempotency_key(chat_id, message, notification_type)

    existing = repo.get_notification_by_key(idempotency_key)
    if existing:
        logger.info("Duplicate notification suppressed (key=%s)", idempotency_key[:12])
        return existing["idempotency_key"]

    nid = repo.add_notification(
        chat_id=chat_id,
        message=message,
        notification_type=notification_type,
        entity_type=entity_type,
        entity_id=entity_id,
        idempotency_key=idempotency_key,
    )
    if nid:
        logger.info("Notification created id=%d type=%s", nid, notification_type)
    return idempotency_key if nid else None


async def send_with_retry(
    notification_id: int,
    bot_send_func,
) -> bool:
    notification = repo.get_notification(notification_id)
    if not notification:
        logger.warning("Notification id=%d not found", notification_id)
        return False
    if notification["status"] == "sent":
        return True

    max_retries = notification["max_retries"]
    for attempt in range(max_retries + 1):
        try:
            await bot_send_func(chat_id=int(notification["chat_id"]), text=notification["message"])
            repo.update_notification(
                notification_id,
                status="sent",
                sent_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            )
            logger.info("Notification id=%d sent successfully", notification_id)
            return True
        except Exception as e:
            retry_count = notification["retry_count"] + 1
            repo.update_notification(notification_id, status="failed", retry_count=retry_count)
            logger.error("Failed to send notification id=%d (attempt %d/%d): %s", notification_id, attempt + 1, max_retries + 1, e)
            if attempt < max_retries:
                wait = 2 ** attempt
                await asyncio.sleep(wait)
            else:
                logger.error("Notification id=%d failed after %d attempts", notification_id, max_retries + 1)
    return False


def mark_as_read(notification_id: int) -> bool:
    result = repo.update_notification(
        notification_id,
        status="read",
        read_at=time.strftime("%Y-%m-%d %H:%M:%S"),
    )
    if result:
        logger.info("Notification id=%d marked as read", notification_id)
    return result


def get_pending_notifications() -> list[dict]:
    return repo.get_pending_notifications()
