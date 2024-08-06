import datetime
from pathlib import Path
from typing import List

from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials

def is_timeslot_str(s: str) -> bool:
    try:
        a, b = s.split('-')
        datetime.datetime.strptime(a, "%H%M")
        datetime.datetime.strptime(b, "%H%M")
        return True
    except ValueError:
        return False

def get_credentials(scopes: List[str], secrets_file: Path) -> Credentials:
    creds = None
    if secrets_file.exists():
        creds = Credentials.from_service_account_file(str(secrets_file), scopes=scopes)
    if not creds:
        raise RuntimeError("Failed to obtain credentials for service account")
    if not creds.valid:
        creds.refresh(Request())
    return creds

