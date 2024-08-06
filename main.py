from __future__ import print_function, annotations

import argparse
from typing import Type, Dict, List, Union
from pathlib import Path
import warnings

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from google.auth import load_credentials_from_file

from admittance import OpeningAdmittance
from data_types import Person, Registration, ProtoTimeslot, LimitedTimeslot, Timeslot
from binding import bind
from interfaces_colab import select_sheet_query

# If modifying these scopes, delete the file token.json.
from util import get_credentials


class AdmittanceSystem:
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    admittance: OpeningAdmittance
    spreadsheet_id: str

    def __init__(self, spreadsheet_id: str, client_secret_file: Path):
        self.spreadsheet_id = spreadsheet_id
        self._client_secret_file = client_secret_file
        self.setup_spreadsheet_connections()

    def setup_spreadsheet_connections(self):
        raw_sheets = {}
        try:
            service = build('sheets', 'v4', credentials=get_credentials(self.SCOPES, self._client_secret_file))

            # Call the Sheets API
            spreadsheets = service.spreadsheets()
            sheet_metadata = spreadsheets.get(spreadsheetId=self.spreadsheet_id).execute()
            sheets = sheet_metadata.get('sheets', '')

            for sheet in sheets:
                sheet_title = sheet.get("properties", {}).get("title", "Unnamed Sheet")
                sheet_id = sheet.get("properties", {}).get("sheetId", 0)
                print('Sheet title: {0}, Sheet ID: {1}'.format(sheet_title, sheet_id))
                raw_sheets[sheet_title] = spreadsheets.values().get(spreadsheetId=self.spreadsheet_id,
                                                                    range=f"{sheet_title}!A1:Z").execute()

        except HttpError as err:
            print(err)
            if err.code == 403:
                print("Does the service account running this script have access to the spreadsheet?", spreadsheet_id)
            exit(1)

        def get_data_from_sheet(datatype: Type, sheet_name=None, promote_func=None):
            if sheet_name not in raw_sheets:
                sheet_name = select_sheet_query(sheets, sheet_name)

            data = raw_sheets[sheet_name].get("values", [])
            headers = data.pop(0)
            data_binding = bind(headers, datatype)
            if data_binding is None:
                print(f"binding column names with {datatype.__name__} failed")
                exit()

            return [promote_func({k: row[v] for k, v in data_binding.items()}) for row in data]

        # TODO: Dont have sheet names plainly in the program but configurable from file instead!
        raw_registrations = get_data_from_sheet(Registration, "Responses", Registration.from_dict)
        opening_details = get_data_from_sheet(ProtoTimeslot, "Timeslot Details", ProtoTimeslot.from_dict)

        self.admittance = OpeningAdmittance(
            timeslots={
                timeslot.name: (Timeslot() if timeslot.unlimited else LimitedTimeslot(timeslot.slots))
                for timeslot in opening_details
            },
            registrations=raw_registrations
        )

        self.admittance.confirmed_duplicates = set(get_data_from_sheet(Person, "Manually Confirmed Duplicates", Person.from_dict))
        self.admittance.confirmed_nonworking_emails = set(get_data_from_sheet(Person, "Confirmed Faulty Emails", Person.from_dict))
        self.admittance.banned = set(get_data_from_sheet(Person, "Ban List", Person.from_dict))

        downprioritised = get_data_from_sheet(Person, "Downprioritised", Person.from_dict)

        for timeslot in self.admittance.timeslots.keys():
            self.admittance.timeslots[timeslot].downprioritised = set(downprioritised)


#    def do_stuff(self):
#        try:
#            service = build('sheets', 'v4', credentials=get_credentials(self.SCOPES))
#
#            # Call the Sheets API
#            spreadsheets = service.spreadsheets()
#            sheet_metadata = spreadsheets.get(spreadsheetId=self.spreadsheet_id).execute()
#            sheets = sheet_metadata.get('sheets', '')
#
#            for sheet in sheets:
#                sheet_title = sheet.get("properties", {}).get("title", "Unnamed Sheet")
#                sheet_id = sheet.get("properties", {}).get("sheetId", 0)
#                print('Sheet title: {0}, Sheet ID: {1}'.format(sheet_title, sheet_id))
#                raw_sheets[sheet_title] = spreadsheets.values().get(spreadsheetId=self.spreadsheet_id,
#                                                                    range=f"{sheet_title}!A1:Z").execute()
#
#        except HttpError as err:
#            print(err)
#            exit(1)

    def pre_process(self):
        """
        Go through registrations and look for duplicate entries,
        emails we suspect will not work etc. Adding people to the Confirmed Duplicates sheet will move their
        latest duplicate into the system for use. This makes it so that the latter entry is the correct one
        if the duplicate was made to correct any errors in their info.
        Additionally, it lets us remove people who tries to abuse the system by having multiple entires added.
        :return:
        """
        self.admittance.preprocess()
        self.admittance.write_to_spreadsheet(self.spreadsheet_id, self._client_secret_file, write_timeslots=False)

    def auto_admit(self):
        """
        Move all registrations into timeslots and waiting lists for said timeslots
        :return:
        """
        while (response := input("Run AutoAdmit? Type 'yes'/'no'\n")) not in ['yes', 'no']:
            pass

        if response == 'yes':
            self.admittance.preprocess()
            self.admittance.auto_admit()
            self.admittance.write_to_spreadsheet(self.spreadsheet_id, self._client_secret_file, write_timeslots=True, write_marked=True)

    def admit_waiting_list(self):
        """
        Remove registrations that have been cancelled from timeslots and waiting lists.
        Remove registrations that have been confirmed as having non-working email addresses
            from timeslots and waiting lists.
        Remove registrations that have been confirmed as duplicates from timeslots and waiting lists.
            (Doing this before auto_admit by running pre_process is ideal!!!)

        Pick out the appropriate number of people from the waiting lists and add them to the
            appropriate timeslot.
        :return:
        """
        # TODO: Warn if non-confirmed duplicates or non-confirmed non-working emails remain by doing preprocess again
        self.admittance.preprocess()

    def data_processing(self):
        """
        Process data given by registrations

        :return:
        """
        print("Data processing is not implemented")

def spreadsheet_string(raw_value: str) -> str:
    # TODO: make more robust
    if (id_start_pos := raw_value.find("docs.google.com/spreadsheets/d/")) != -1:
        id_start_pos += len("docs.google.com/spreadsheets/d/")
        # select the string from after '/d/' until we hit another '/' character
        return raw_value[id_start_pos:].split("/")[0]
    return raw_value

# The ID and range of a sample spreadsheet.
DEFAULT_SPREADSHEET_ID = '1Th4fyC3-LqV5u9-KIoDviUU_Bwce9TUyH9HQkhqm0NU'
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sheet", type=spreadsheet_string, default=DEFAULT_SPREADSHEET_ID, help="Sheet ID or URL")
    parser.add_argument("--secret", "-s", type=Path, default=Path("client_secret.json"), help="Authentication secrets for service account")
    subparsers = parser.add_subparsers(title="modes", description="modes", help="help", required=True)
    pp_parser = subparsers.add_parser('pp', description="pre process registrations")
    aa_parser = subparsers.add_parser('aa', description="auto-admit registrations")
    dp_parser = subparsers.add_parser('dp', description="data processing registrations")
    pp_parser.set_defaults(run_mode=lambda system: system.pre_process())
    aa_parser.set_defaults(run_mode=lambda system: system.auto_admit())
    dp_parser.set_defaults(run_mode=lambda system: system.data_processing())

    args = parser.parse_args()
    print(args.sheet)
    admittance_system = AdmittanceSystem(args.sheet, args.secret)
    args.run_mode(admittance_system)


if __name__ == '__main__':
    main()
