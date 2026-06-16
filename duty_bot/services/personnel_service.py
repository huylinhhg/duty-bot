import json
import logging
from typing import Any, Optional

import duty_bot.database.repository as repo
from duty_bot.models.entities import Personnel

logger = logging.getLogger(__name__)

def add_personnel(name: str, position: str = "", group_name: str = "") -> Personnel:
    pid = repo.add_personnel(name, position, group_name)
    repo.add_audit_log("create_personnel", "personnel", pid, json.dumps({"name": name, "position": position, "group_name": group_name}, ensure_ascii=False))
    logger.info("Added personnel: %s (id=%d)", name, pid)
    return Personnel(id=pid, name=name, position=position, group_name=group_name)


def get_personnel(personnel_id: Optional[int] = None) -> list[dict[str, Any]]:
    return repo.get_personnel(personnel_id)


def get_active_personnel() -> list[dict[str, Any]]:
    return repo.get_active_personnel()


def deactivate_personnel(personnel_id: int) -> bool:
    result = repo.update_personnel(personnel_id, is_active=0)
    if result:
        repo.add_audit_log("deactivate_personnel", "personnel", personnel_id, "{}")
        logger.info("Deactivated personnel id=%d", personnel_id)
    return result


def add_exclusion(personnel_id: int, start_date: str, end_date: str, reason: str = "") -> int:
    eid = repo.add_exclusion(personnel_id, start_date, end_date, reason)
    repo.add_audit_log("create_exclusion", "exclusion", eid, json.dumps({"personnel_id": personnel_id, "start": start_date, "end": end_date}, ensure_ascii=False))
    logger.info("Added exclusion for personnel_id=%d: %s -> %s", personnel_id, start_date, end_date)
    return eid


def get_exclusions(personnel_id: Optional[int] = None, date_from: Optional[str] = None, date_to: Optional[str] = None) -> list[dict[str, Any]]:
    return repo.get_exclusions(personnel_id, date_from, date_to)


def is_available(personnel_id: int, date_str: str) -> bool:
    return not repo.is_excluded_on_date(personnel_id, date_str)


def create_group(name: str, description: str = "") -> dict[str, Any]:
    gid = repo.add_group(name, description)
    repo.add_audit_log("create_group", "group", gid, json.dumps({"name": name}, ensure_ascii=False))
    logger.info("Created group: %s (id=%d)", name, gid)
    return {"id": gid, "name": name, "description": description}


def add_to_group(group_id: int, personnel_id: int) -> bool:
    rid = repo.add_group_member(group_id, personnel_id)
    if rid:
        repo.add_audit_log("add_group_member", "group_member", rid, json.dumps({"group_id": group_id, "personnel_id": personnel_id}))
        return True
    return False


def get_groups() -> list[dict[str, Any]]:
    return repo.get_groups()


def get_group_members(group_id: int) -> list[dict[str, Any]]:
    return repo.get_group_members(group_id)


def validate_personnel_id(personnel_id: int) -> Optional[dict[str, Any]]:
    people = repo.get_personnel(personnel_id)
    return people[0] if people else None


def find_personnel_by_name(name: str) -> Optional[dict[str, Any]]:
    all_p = repo.get_personnel()
    for p in all_p:
        if p["name"].lower() == name.lower().strip():
            return p
    return None
