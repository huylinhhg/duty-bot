from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Personnel:
    id: Optional[int] = None
    name: str = ""
    position: str = ""
    group_name: str = ""
    is_active: int = 1
    created_at: str = ""


@dataclass
class DutyGroup:
    id: Optional[int] = None
    name: str = ""
    description: str = ""


@dataclass
class DutySchedule:
    id: Optional[int] = None
    date: str = ""
    shift: str = ""
    personnel_id: int = 0
    group_name: str = ""
    status: str = "draft"
    source: str = "auto"
    week_number: Optional[int] = None
    created_at: str = ""
    updated_at: str = ""
    personnel_name: str = ""


@dataclass
class DutyExclusion:
    id: Optional[int] = None
    personnel_id: int = 0
    start_date: str = ""
    end_date: str = ""
    reason: str = ""
    created_at: str = ""
    personnel_name: str = ""


@dataclass
class Approval:
    id: Optional[int] = None
    week_start: str = ""
    week_end: str = ""
    status: str = "draft"
    approver_id: Optional[int] = None
    approved_at: Optional[str] = None
    comment: str = ""
    created_at: str = ""
    updated_at: str = ""
    approver_name: str = ""


@dataclass
class AuditLog:
    id: Optional[int] = None
    action: str = ""
    entity_type: str = ""
    entity_id: Optional[int] = None
    payload: str = ""
    created_at: str = ""


@dataclass
class Notification:
    id: Optional[int] = None
    chat_id: str = ""
    message: str = ""
    status: str = "pending"
    notification_type: str = ""
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    retry_count: int = 0
    max_retries: int = 3
    idempotency_key: Optional[str] = None
    sent_at: Optional[str] = None
    read_at: Optional[str] = None
    created_at: str = ""
