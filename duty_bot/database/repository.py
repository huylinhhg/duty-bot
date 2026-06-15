import json
import logging
from datetime import datetime
from typing import Any, Optional

from duty_bot.database.connection import get_db

logger = logging.getLogger(__name__)


def add_personnel(name: str, position: str = "", group_name: str = "") -> int:
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO personnel (name, position, group_name) VALUES (?, ?, ?)",
            (name, position, group_name),
        )
        return cur.lastrowid


def get_personnel(personnel_id: Optional[int] = None) -> list[dict[str, Any]]:
    with get_db() as conn:
        if personnel_id:
            rows = conn.execute(
                "SELECT * FROM personnel WHERE id = ?", (personnel_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM personnel ORDER BY group_name, position, name"
            ).fetchall()
        return [dict(r) for r in rows]


def get_active_personnel() -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM personnel WHERE is_active = 1 ORDER BY group_name, position, name"
        ).fetchall()
        return [dict(r) for r in rows]


def update_personnel(personnel_id: int, **kwargs: Any) -> bool:
    if not kwargs:
        return False
    fields = []
    values = []
    for k, v in kwargs.items():
        if k in ("name", "position", "group_name", "is_active"):
            fields.append(f"{k} = ?")
            values.append(v)
    if not fields:
        return False
    values.append(personnel_id)
    with get_db() as conn:
        cur = conn.execute(
            f"UPDATE personnel SET {', '.join(fields)} WHERE id = ?", values
        )
        return cur.rowcount > 0


def delete_personnel(personnel_id: int) -> bool:
    with get_db() as conn:
        cur = conn.execute("DELETE FROM personnel WHERE id = ?", (personnel_id,))
        return cur.rowcount > 0


def add_group(name: str, description: str = "") -> int:
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO duty_groups (name, description) VALUES (?, ?)",
            (name, description),
        )
        return cur.lastrowid


def get_groups() -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM duty_groups ORDER BY name").fetchall()
        return [dict(r) for r in rows]


def add_group_member(group_id: int, personnel_id: int) -> int:
    with get_db() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO group_members (group_id, personnel_id) VALUES (?, ?)",
            (group_id, personnel_id),
        )
        return cur.lastrowid


def get_group_members(group_id: int) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT p.* FROM group_members gm
               JOIN personnel p ON p.id = gm.personnel_id
               WHERE gm.group_id = ? ORDER BY p.name""",
            (group_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_schedule_by_id(schedule_id: int) -> Optional[dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute(
            """SELECT ds.*, p.name as personnel_name FROM duty_schedules ds
               JOIN personnel p ON p.id = ds.personnel_id
               WHERE ds.id = ?""",
            (schedule_id,),
        ).fetchone()
        return dict(row) if row else None


def add_schedule(
    date: str,
    shift: str,
    personnel_id: int,
    group_name: str = "",
    status: str = "draft",
    source: str = "auto",
    week_number: Optional[int] = None,
) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO duty_schedules (date, shift, personnel_id, group_name, status, source, week_number)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (date, shift, personnel_id, group_name, status, source, week_number),
        )
        return cur.lastrowid


def get_schedules_by_date(date_str: str) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT ds.*, p.name as personnel_name FROM duty_schedules ds
               JOIN personnel p ON p.id = ds.personnel_id
               WHERE ds.date = ? ORDER BY ds.shift""",
            (date_str,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_schedules_by_date_range(start_date: str, end_date: str) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT ds.*, p.name as personnel_name FROM duty_schedules ds
               JOIN personnel p ON p.id = ds.personnel_id
               WHERE ds.date BETWEEN ? AND ? ORDER BY ds.date, ds.shift""",
            (start_date, end_date),
        ).fetchall()
        return [dict(r) for r in rows]


def get_week_schedules(year: int, week: int) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT ds.*, p.name as personnel_name FROM duty_schedules ds
               JOIN personnel p ON p.id = ds.personnel_id
               WHERE ds.week_number = ? AND strftime('%Y', ds.date) = ?
               ORDER BY ds.date, ds.shift""",
            (week, str(year)),
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_schedules() -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT ds.*, p.name as personnel_name FROM duty_schedules ds
               JOIN personnel p ON p.id = ds.personnel_id
               ORDER BY ds.date, ds.shift"""
        ).fetchall()
        return [dict(r) for r in rows]


def update_schedule_status_by_week(
    week_start: str, week_end: str, status: str
) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """UPDATE duty_schedules SET status = ?, updated_at = CURRENT_TIMESTAMP
               WHERE date BETWEEN ? AND ?""",
            (status, week_start, week_end),
        )
        return cur.rowcount


def update_schedule(schedule_id: int, **kwargs: Any) -> bool:
    if not kwargs:
        return False
    fields = []
    values = []
    for k, v in kwargs.items():
        if k in ("status", "source", "shift", "date", "personnel_id", "group_name"):
            fields.append(f"{k} = ?")
            values.append(v)
    if not fields:
        return False
    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.append(schedule_id)
    with get_db() as conn:
        cur = conn.execute(
            f"UPDATE duty_schedules SET {', '.join(fields)} WHERE id = ?", values
        )
        return cur.rowcount > 0


def delete_schedule(schedule_id: int) -> bool:
    with get_db() as conn:
        cur = conn.execute("DELETE FROM duty_schedules WHERE id = ?", (schedule_id,))
        return cur.rowcount > 0


def count_schedules_in_range(start_date: str, end_date: str) -> int:
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM duty_schedules WHERE date BETWEEN ? AND ?",
            (start_date, end_date),
        ).fetchone()
        return row["cnt"]


def get_personnel_shift_count(
    start_date: str, end_date: str
) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT p.id, p.name, COUNT(ds.id) as shift_count
               FROM personnel p LEFT JOIN duty_schedules ds
               ON ds.personnel_id = p.id AND ds.date BETWEEN ? AND ?
               GROUP BY p.id ORDER BY shift_count DESC""",
            (start_date, end_date),
        ).fetchall()
        return [dict(r) for r in rows]


def add_exclusion(
    personnel_id: int, start_date: str, end_date: str, reason: str = ""
) -> int:
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO duty_exclusions (personnel_id, start_date, end_date, reason) VALUES (?, ?, ?, ?)",
            (personnel_id, start_date, end_date, reason),
        )
        return cur.lastrowid


def get_exclusions(
    personnel_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> list[dict[str, Any]]:
    with get_db() as conn:
        query = "SELECT de.*, p.name as personnel_name FROM duty_exclusions de JOIN personnel p ON p.id = de.personnel_id WHERE 1=1"
        params = []
        if personnel_id is not None:
            query += " AND de.personnel_id = ?"
            params.append(personnel_id)
        if date_from is not None:
            query += " AND de.end_date >= ?"
            params.append(date_from)
        if date_to is not None:
            query += " AND de.start_date <= ?"
            params.append(date_to)
        query += " ORDER BY de.start_date"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def is_excluded_on_date(personnel_id: int, date_str: str) -> bool:
    with get_db() as conn:
        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM duty_exclusions
               WHERE personnel_id = ? AND start_date <= ? AND end_date >= ?""",
            (personnel_id, date_str, date_str),
        ).fetchone()
        return row["cnt"] > 0


def add_approval(
    week_start: str,
    week_end: str,
    status: str = "draft",
    approver_id: Optional[int] = None,
) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO approvals (week_start, week_end, status, approver_id)
               VALUES (?, ?, ?, ?)""",
            (week_start, week_end, status, approver_id),
        )
        return cur.lastrowid


def get_approval(approval_id: int) -> Optional[dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute(
            """SELECT a.*, ap.name as approver_name FROM approvals a
               LEFT JOIN personnel ap ON ap.id = a.approver_id
               WHERE a.id = ?""",
            (approval_id,),
        ).fetchone()
        return dict(row) if row else None


def get_approval_by_week(week_start: str) -> Optional[dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM approvals WHERE week_start = ?", (week_start,)
        ).fetchone()
        return dict(row) if row else None


def get_pending_approvals() -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM approvals WHERE status = 'pending_approval'
               ORDER BY week_start""",
        ).fetchall()
        return [dict(r) for r in rows]


def get_approval_history(limit: int = 20) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM approvals ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def update_approval(approval_id: int, **kwargs: Any) -> bool:
    if not kwargs:
        return False
    fields = []
    values = []
    for k, v in kwargs.items():
        if k in ("status", "approver_id", "approved_at", "comment"):
            fields.append(f"{k} = ?")
            values.append(v)
    if not fields:
        return False
    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.append(approval_id)
    with get_db() as conn:
        cur = conn.execute(
            f"UPDATE approvals SET {', '.join(fields)} WHERE id = ?", values
        )
        return cur.rowcount > 0


def get_pending_approval_weeks() -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT ds.date, strftime('%Y', ds.date) as year,
               ds.week_number, COUNT(*) as total
               FROM duty_schedules ds
               WHERE ds.status = 'draft'
               GROUP BY ds.week_number
               ORDER BY ds.date LIMIT 1"""
        ).fetchall()
        return [dict(r) for r in rows]


def add_audit_log(
    action: str, entity_type: str, entity_id: Optional[int] = None, payload: str = ""
) -> int:
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO audit_log (action, entity_type, entity_id, payload) VALUES (?, ?, ?, ?)",
            (action, entity_type, entity_id, payload),
        )
        return cur.lastrowid


def get_audit_logs(
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    with get_db() as conn:
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []
        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)
        if entity_id is not None:
            query += " AND entity_id = ?"
            params.append(entity_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def add_notification(
    chat_id: str,
    message: str,
    notification_type: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    idempotency_key: Optional[str] = None,
) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT OR IGNORE INTO notifications
               (chat_id, message, status, notification_type, entity_type, entity_id, idempotency_key)
               VALUES (?, ?, 'pending', ?, ?, ?, ?)""",
            (chat_id, message, notification_type, entity_type, entity_id, idempotency_key),
        )
        return cur.lastrowid


def get_notification(notification_id: int) -> Optional[dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM notifications WHERE id = ?", (notification_id,)
        ).fetchone()
        return dict(row) if row else None


def get_pending_notifications() -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM notifications
               WHERE status IN ('pending', 'failed') AND retry_count < max_retries
               ORDER BY created_at""",
        ).fetchall()
        return [dict(r) for r in rows]


def update_notification(notification_id: int, **kwargs: Any) -> bool:
    if not kwargs:
        return False
    fields = []
    values = []
    for k, v in kwargs.items():
        if k in ("status", "retry_count", "sent_at", "read_at"):
            fields.append(f"{k} = ?")
            values.append(v)
    if not fields:
        return False
    values.append(notification_id)
    with get_db() as conn:
        cur = conn.execute(
            f"UPDATE notifications SET {', '.join(fields)} WHERE id = ?", values
        )
        return cur.rowcount > 0


def get_notification_by_key(idempotency_key: str) -> Optional[dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM notifications WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        return dict(row) if row else None


def get_rotation_state(group_name: str, shift: str) -> Optional[dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM rotation_state WHERE group_name = ? AND shift = ?",
            (group_name, shift),
        ).fetchone()
        return dict(row) if row else None


def set_rotation_state(group_name: str, shift: str, last_position: int) -> bool:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO rotation_state (group_name, shift, last_position, updated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(group_name, shift)
               DO UPDATE SET last_position = ?, updated_at = CURRENT_TIMESTAMP""",
            (group_name, shift, last_position, last_position),
        )
        return cur.rowcount > 0


def get_app_state(key: str) -> Optional[str]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT value FROM app_state WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None


def set_app_state(key: str, value: str) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO app_state (key, value) VALUES (?, ?)",
            (key, value),
        )
