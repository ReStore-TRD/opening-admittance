from __future__ import print_function

import json
import os.path
from typing import Type, Dict, List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from admittance import OpeningAdmittance
from data_types import Person, Registration, ProtoTimeslot, LimitedTimeslot, Timeslot
from binding import bind
from interfaces import (
    open_admittance_creation_window,
    open_spreadsheet_dialog_window,
    open_select_sheet_dialog_window,
)

import re

# If modifying these scopes, delete the file token.json.
from util import get_credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# The ID and range of a sample spreadsheet.
SPREADSHEET_ID = "1s6OUJOPaLbF4i6ZF3wPdW6Lkp5ghgbgUsEzlcj9ukWo"
SAMPLE_RANGE_NAME = "Responses!A1:Z"


def main():
    raw_sheets = {}

    try:
        service = build("sheets", "v4", credentials=get_credentials(SCOPES))

        # Call the Sheets API
        spreadsheets = service.spreadsheets()
        sheet_metadata = spreadsheets.get(spreadsheetId=SPREADSHEET_ID).execute()
        sheets = sheet_metadata.get("sheets", "")

        for sheet in sheets:
            sheet_title = sheet.get("properties", {}).get("title", "Unnamed Sheet")
            sheet_id = sheet.get("properties", {}).get("sheetId", 0)
            print("Sheet title: {0}, Sheet ID: {1}".format(sheet_title, sheet_id))
            raw_sheets[sheet_title] = (
                spreadsheets.values()
                .get(spreadsheetId=SPREADSHEET_ID, range=f"{sheet_title}!A1:Z")
                .execute()
            )

    except HttpError as err:
        print(err)
        exit(1)

    registrations_data = raw_sheets["Responses"].get("values", [])
    headers = registrations_data.pop(0)
    data_binding = bind(headers, Registration)
    if data_binding is None:
        print("Binding column names with registration entries failed")
        exit()

    unprocessed_entries = [
        Registration.from_dict({k: row[v] for k, v in data_binding.items()})
        for row in registrations_data
    ]

    # TODO: Dont have this written plainly in the program but configurable from file instead!
    admittance_details_sheet = "Timeslot Details"
    if admittance_details_sheet not in raw_sheets:
        admittance_details_sheet = open_select_sheet_dialog_window(SPREADSHEET_ID)

    admittance_details_data = raw_sheets[admittance_details_sheet].get("values", [])
    headers = admittance_details_data.pop(0)
    data_binding = bind(headers, ProtoTimeslot)

    if data_binding is None:
        print("Binding column names with admittance details entries failed")
        exit()

    admittance_details = [
        ProtoTimeslot.from_dict({k: row[v] for k, v in data_binding.items()})
        for row in admittance_details_data
    ]

    admittance = OpeningAdmittance(
        {
            timeslot.name: (
                Timeslot() if timeslot.unlimited else LimitedTimeslot(timeslot.slots)
            )
            for timeslot in admittance_details
        }
    )

    admittance_confirmed_duplicates_sheet = "confirmed duplicates"
    if admittance_confirmed_duplicates_sheet not in raw_sheets:
        admittance_confirmed_duplicates_sheet = open_select_sheet_dialog_window(
            SPREADSHEET_ID
        )

    admittance_confirmed_duplicates_data = raw_sheets[
        admittance_confirmed_duplicates_sheet
    ].get("values", [])
    headers = admittance_confirmed_duplicates_data.pop(0)
    data_binding = bind(headers, Person)

    if data_binding is None:
        print("Binding column names with confirmed duplicates entries failed")
        exit()

    confirmed_duplicates = set(
        Person.from_dict({k: row[v] for k, v in data_binding.items()})
        for row in admittance_confirmed_duplicates_data
    )
    admittance.confirmed_duplicates = confirmed_duplicates

    admittance_confirmed_nonworking_email_sheet = "non-working emails"
    if admittance_confirmed_nonworking_email_sheet not in raw_sheets:
        admittance_confirmed_nonworking_email_sheet = open_select_sheet_dialog_window(
            SPREADSHEET_ID
        )

    admittance_confirmed_nonworking_email_data = raw_sheets[
        admittance_confirmed_nonworking_email_sheet
    ].get("values", [])
    headers = admittance_confirmed_nonworking_email_data.pop(0)
    data_binding = bind(headers, Person)

    if data_binding is None:
        print("Binding column names with confirmed duplicates entries failed")
        exit()

    confirmed_nonworking_emails = set(
        Person.from_dict({k: row[v] for k, v in data_binding.items()})
        for row in admittance_confirmed_nonworking_email_data
    )
    admittance.confirmed_nonworking_emails = confirmed_nonworking_emails

    admittance.auto_admit(unprocessed_entries)

    admittance.write_to_spreadsheet(SPREADSHEET_ID)


if __name__ == "__main__":
    main()
