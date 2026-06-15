import json
import logging
from datetime import datetime
from typing import Any, Optional

import duty_bot.database.repository as repo
from duty_bot.models.entities import Approval

logger = logging.getLogger(__name__)


def submit_for_approval(week_start: str, week_end: str) -> Optional[Approval]:
    existing = repo.get_approval_by_week(week_start)
    if existing:
        logger.warning("Week %s already has approval id=%d", week_start, existing["id"])
        return None

    aid = repo.add_approval(week_start, week_end, status="pending_approval")
    updated = repo.update_schedule_status_by_week(week_start, week_end, "pending_approval")
    audit_payload = json.dumps({"week_start": week_start, "week_end": week_end, "schedules_updated": updated}, ensure_ascii=False)
    repo.add_audit_log("submit_approval", "approval", aid, audit_payload)
    logger.info("Submitted week %s - %s for approval (id=%d, %d schedules)", week_start, week_end, aid, updated)
    return Approval(id=aid, week_start=week_start, week_end=week_end, status="pending_approval")


def approve(approval_id: int, approver_id: int, comment: str = "") -> bool:
    approval = repo.get_approval(approval_id)
    if not approval:
        logger.warning("Approval id=%d not found", approval_id)
        return False
    if approval["status"] != "pending_approval":
        logger.warning("Approval id=%d has status %s, cannot approve", approval_id, approval["status"])
        return False

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    repo.update_approval(approval_id, status="approved", approver_id=approver_id, approved_at=now, comment=comment)
    repo.update_schedule_status_by_week(approval["week_start"], approval["week_end"], "approved")
    audit_payload = json.dumps({"approver_id": approver_id, "comment": comment}, ensure_ascii=False)
    repo.add_audit_log("approve", "approval", approval_id, audit_payload)
    logger.info("Approval id=%d approved by %d", approval_id, approver_id)
    return True


def reject(approval_id: int, approver_id: int, comment: str = "") -> bool:
    approval = repo.get_approval(approval_id)
    if not approval:
        logger.warning("Approval id=%d not found", approval_id)
        return False
    if approval["status"] != "pending_approval":
        logger.warning("Approval id=%d has status %s, cannot reject", approval_id, approval["status"])
        return False

    repo.update_approval(approval_id, status="rejected", approver_id=approver_id, comment=comment)
    repo.update_schedule_status_by_week(approval["week_start"], approval["week_end"], "draft")
    audit_payload = json.dumps({"approver_id": approver_id, "comment": comment}, ensure_ascii=False)
    repo.add_audit_log("reject", "approval", approval_id, audit_payload)
    logger.info("Approval id=%d rejected by %d", approval_id, approver_id)
    return True


def get_pending_approvals() -> list[dict[str, Any]]:
    return repo.get_pending_approvals()


def get_approval_history() -> list[dict[str, Any]]:
    return repo.get_approval_history()


def get_approval(approval_id: int) -> Optional[dict[str, Any]]:
    return repo.get_approval(approval_id)


def get_approval_for_week_schedule(year: int, week: int) -> Optional[dict[str, Any]]:
    from datetime import date as date_type
    week_start = date_type.fromisocalendar(year, week, 1).strftime("%Y-%m-%d")
    return repo.get_approval_by_week(week_start)
