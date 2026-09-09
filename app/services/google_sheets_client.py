import re

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from app.config import GOOGLE_SERVICE_ACCOUNT_FILE

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

_service = None


def _get_service():
    global _service
    if _service is None:
        creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        _service = build("sheets", "v4", credentials=creds)
    return _service


def extract_sheet_id(url_or_id: str) -> str:
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", url_or_id)
    return match.group(1) if match else url_or_id


def get_range(sheet_id: str, cell_range: str) -> list[list[str]]:
    service = _get_service()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range=cell_range)
        .execute()
    )
    return result.get("values", [])
