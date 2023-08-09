from __future__ import print_function

import sys
from typing import Type, Dict, List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from admittance import OpeningAdmittance
from data_types import Person, Registration, ProtoTimeslot, LimitedTimeslot, Timeslot
from binding import bind
from interfaces import open_select_sheet_dialog_window

import re

# If modifying these scopes, delete the file token.json.
from util import get_credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def fetch_raw_sheets(sid: str) -> Dict:
    raw_sheets = {}
    try:
        service = build("sheets", "v4", credentials=get_credentials(SCOPES))

        # Call the Sheets API
        spreadsheets = service.spreadsheets()
        sheet_metadata = spreadsheets.get(spreadsheetId=sid).execute()
        sheets = sheet_metadata.get("sheets", "")

        for sheet in sheets:
            sheet_title = sheet.get("properties", {}).get("title", "Unnamed Sheet")
            sheet_id = sheet.get("properties", {}).get("sheetId", 0)
            print("Sheet title: {0}, Sheet ID: {1}".format(sheet_title, sheet_id))
            raw_sheets[sheet_title] = (
                spreadsheets.values()
                .get(spreadsheetId=sid, range=f"{sheet_title}!A1:Z")
                .execute()
            )
        return raw_sheets

    except HttpError as err:
        print(err)
        exit(1)


def main(spreadsheet_id: str, only_preprocess: bool):
    raw_sheets = fetch_raw_sheets(spreadsheet_id)

    # Read and bind Responses columns to meaningful fields
    responses_sheet = "Responses"
    if responses_sheet not in raw_sheets:
        responses_sheet = open_select_sheet_dialog_window(
            spreadsheet_id, "Select 'Responses' Sheet"
        )
        # TODO: check to see if need to refetch raw_sheets

    registrations_data = raw_sheets[responses_sheet].get("values", [])
    headers = registrations_data.pop(0)
    data_binding = bind(headers, Registration)
    if data_binding is None:
        print("Binding column names with registration entries failed")
        exit()

    unprocessed_entries = [
        Registration.from_dict({k: row[v] for k, v in data_binding.items()})
        for row in registrations_data
    ]

    # Read and bind Timeslot Details columns to meaningful fields
    timeslot_details_sheet = "Timeslot Details"
    if timeslot_details_sheet not in raw_sheets:
        timeslot_details_sheet = open_select_sheet_dialog_window(
            spreadsheet_id, "Select 'Timeslot Details' Sheet"
        )

    timeslot_details_data = raw_sheets[timeslot_details_sheet].get("values", [])
    headers = timeslot_details_data.pop(0)
    data_binding = bind(headers, ProtoTimeslot)

    if data_binding is None:
        print("Binding column names with admittance details entries failed")
        exit()

    timeslot_details = [
        ProtoTimeslot.from_dict({k: row[v] for k, v in data_binding.items()})
        for row in timeslot_details_data
    ]

    admittance = OpeningAdmittance(
        {
            timeslot.name: (
                Timeslot() if timeslot.unlimited else LimitedTimeslot(timeslot.capacity)
            )
            for timeslot in timeslot_details
        }
    )

    # Read Confirmed Duplicates
    admittance_confirmed_duplicates_sheet = "Confirmed Duplicates"
    if admittance_confirmed_duplicates_sheet not in raw_sheets:
        admittance_confirmed_duplicates_sheet = open_select_sheet_dialog_window(
            spreadsheet_id, "Select 'Confirmed Duplicates' sheet"
        )
        if admittance_confirmed_duplicates_sheet not in raw_sheets:
            raw_sheets = fetch_raw_sheets(spreadsheet_id)

    if admittance_confirmed_duplicates_data := raw_sheets[
        admittance_confirmed_duplicates_sheet
    ].get("values"):
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

    # Read Non-working emails
    admittance_confirmed_nonworking_email_sheet = "Non-working Emails"
    if admittance_confirmed_nonworking_email_sheet not in raw_sheets:
        admittance_confirmed_nonworking_email_sheet = open_select_sheet_dialog_window(
            spreadsheet_id, "Select 'non-working emails' sheet"
        )
        if admittance_confirmed_nonworking_email_sheet not in raw_sheets:
            raw_sheets = fetch_raw_sheets(spreadsheet_id)

    if admittance_confirmed_nonworking_email_data := raw_sheets[
        admittance_confirmed_nonworking_email_sheet
    ].get("values"):
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

    # Admit everyone
    admittance.auto_admit(unprocessed_entries)

    admittance.write_to_spreadsheet(spreadsheet_id, only_preprocess)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            f"Wrong number of arguments, expected 1 got {len(sys.argv) - 1}: {sys.argv[1:]}"
            "Spreadsheet ID not provided!"
        )
        exit()
    if len(sys.argv) > 3:
        f"Wrong number of arguments, expected 1 got {len(sys.argv) - 1}: {sys.argv[1:]}"
        exit()
    run_fully = len(sys.argv) == 3 and sys.argv[2].lower() == "doit"
    main(sys.argv[1], not run_fully)
