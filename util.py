import datetime
import os.path
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

def get_credentials(scopes: List[str]) -> Credentials:
    creds = None
    if os.path.exists('client_secret.json'):
        creds = Credentials.from_service_account_file('client_secret.json', scopes=scopes)
    if not creds:
        raise RuntimeError("Failed to obtain credentials for service account")
    if not creds.valid:
        creds.refresh(Request())
    return creds

