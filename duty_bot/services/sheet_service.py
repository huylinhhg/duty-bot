import logging
from typing import Any, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build

import duty_bot.database.repository as repo

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_FILE = "service_account.json"


def get_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("sheets", "v4", credentials=creds)


def export_to_sheet(spreadsheet_id: str, rows: Optional[list[dict]] = None) -> bool:
    try:
        if rows is None:
            rows = repo.get_all_schedules()
        if not rows:
            logger.warning("No data to export")
            return False

        service = get_service()
        values = [["Ngày", "Ca", "Tên CBCS", "Tổ", "Trạng thái", "Nguồn"]]
        for r in rows:
            values.append([
                r.get("date", ""),
                r.get("shift", ""),
                r.get("personnel_name", ""),
                r.get("group_name", ""),
                r.get("status", ""),
                r.get("source", ""),
            ])
        body = {"values": values}
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="Sheet1!A:F",
            valueInputOption="RAW",
            body=body,
        ).execute()
        logger.info("Exported %d rows to sheet %s", len(rows), spreadsheet_id)
        return True
    except Exception as e:
        logger.error("Failed to export to sheet: %s", e)
        return False


def import_from_sheet(spreadsheet_id: str) -> list[dict[str, Any]]:
    try:
        service = get_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="Sheet1!A:E",
        ).execute()
        values = result.get("values", [])
        if not values or len(values) < 2:
            return []

        imported = []
        for row in values[1:]:
            if len(row) >= 3:
                person = repo.get_personnel()
                name = row[2] if len(row) > 2 else ""
                p = next((x for x in person if x["name"].lower() == name.strip().lower()), None)
                if not p:
                    logger.warning("Personnel not found for name: %s", name)
                    continue
                imported.append({
                    "date": row[0],
                    "shift": row[1],
                    "personnel_id": p["id"],
                    "group_name": p.get("group_name", ""),
                    "status": row[4] if len(row) > 4 else "draft",
                    "source": "imported",
                })
        logger.info("Imported %d rows from sheet %s", len(imported), spreadsheet_id)
        return imported
    except Exception as e:
        logger.error("Failed to import from sheet: %s", e)
        return []
